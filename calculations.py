"""
Core calculation functions for NPS Rolling Returns analysis.
XIRR logic is identical to the MF calculator.
Additions vs MF version:
  - calculate_lumpsum_rolling()  — rolling lumpsum XIRR across all start dates
  - salary_day filter parameter  — restrict SIP start dates to a specific day of month
"""

import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Tuple, Optional

from config import (
    MAX_XIRR_ITERATIONS,
    XIRR_TOLERANCE,
    XIRR_INITIAL_RATE,
    XIRR_VALIDATION_TOLERANCE,
    DAYS_PER_YEAR,
    PROGRESS_UPDATE_INTERVAL,
    DEFAULT_SIP_AMOUNT,
)


# ══════════════════════════════════════════════════════════════════════════════
# XIRR (unchanged from MF calculator)
# ══════════════════════════════════════════════════════════════════════════════

def xirr(cashflows: List[float], dates: List[datetime]) -> float:
    """
    Calculate Internal Rate of Return using Newton-Raphson method.

    Args:
        cashflows: Negative for investments, positive for returns.
        dates:     Matching list of datetime objects.

    Returns:
        Annual IRR as a decimal (0.12 = 12%). Returns np.nan on failure.
    """
    if len(cashflows) < 2:
        return np.nan

    def npv(rate: float) -> float:
        t0 = dates[0]
        return sum(cf / (1 + rate) ** ((d - t0).days / DAYS_PER_YEAR)
                   for cf, d in zip(cashflows, dates))

    def derivative(rate: float) -> float:
        t0 = dates[0]
        total = 0.0
        for cf, d in zip(cashflows, dates):
            t = (d - t0).days / DAYS_PER_YEAR
            total -= t * cf / (1 + rate) ** (t + 1)
        return total

    rate = XIRR_INITIAL_RATE
    for _ in range(MAX_XIRR_ITERATIONS):
        drv = derivative(rate)
        if drv == 0:
            break
        adj = npv(rate) / drv
        rate -= adj
        if rate <= -1.0:
            rate = -0.9999
        if abs(adj) < XIRR_TOLERANCE:
            break

    redemption = abs(cashflows[-1])
    return rate if abs(npv(rate)) < redemption * XIRR_VALIDATION_TOLERANCE else np.nan


# ══════════════════════════════════════════════════════════════════════════════
# NAV ARRAY HELPERS (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

def build_nav_arrays(nav_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Convert NAV DataFrame to numpy arrays for fast binary-search lookups."""
    return (nav_df['date'].values.astype('datetime64[ns]'),
            nav_df['nav'].values)


def get_next_nav_fast(nav_dates: np.ndarray, nav_vals: np.ndarray,
                      target: datetime) -> Tuple[Optional[pd.Timestamp], Optional[float]]:
    """
    Find the next available NAV on or after target date (binary search).

    Returns:
        (nav_date, nav_value) or (None, None) if no date exists on/after target.
    """
    idx = np.searchsorted(nav_dates, np.datetime64(target, 'ns'), side='left')
    if idx >= len(nav_dates):
        return None, None
    return pd.Timestamp(nav_dates[idx]), nav_vals[idx]


# ══════════════════════════════════════════════════════════════════════════════
# ROLLING SIP (salary_day filter added)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_all_possible_rolling_sip(
    nav_df_json: str,
    years: int,
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
    sip_amount: int = DEFAULT_SIP_AMOUNT,
    salary_day: Optional[int] = None,
    on_progress=None,
) -> pd.DataFrame:
    """
    Calculate rolling SIP returns for all possible start dates in the range.

    Args:
        nav_df_json:  NAV DataFrame serialised as JSON.
        years:        Rolling period in years.
        range_start:  Earliest possible SIP start date.
        range_end:    Latest possible SIP start date.
        sip_amount:   Monthly SIP amount in rupees.
        salary_day:   If set (1–28), only use start dates where day == salary_day.
                      The next available NAV on/after that day is used if it falls
                      on a holiday — identical to standard holiday handling.
        on_progress:  Optional callback(float 0–1) for progress updates.

    Returns:
        DataFrame with: Start Date, End Date, Redemption Date, Instalments, XIRR %, Final Value.
        Empty DataFrame if insufficient data.
    """
    nav_df = pd.read_json(nav_df_json)
    nav_df['date'] = pd.to_datetime(nav_df['date'])

    if nav_df.empty:
        return pd.DataFrame()

    nav_df = nav_df.sort_values('date').reset_index(drop=True)
    months_target = years * 12
    nav_dates, nav_vals = build_nav_arrays(nav_df)

    snapped_start, _ = get_next_nav_fast(nav_dates, nav_vals, range_start)
    if snapped_start is None:
        return pd.DataFrame()

    max_start = range_end - relativedelta(months=months_target - 1)

    # All candidate start dates within the NAV data
    start_candidates = nav_df[
        (nav_df['date'] >= snapped_start) &
        (nav_df['date'] <= max_start)
    ]['date'].reset_index(drop=True)

    # ── Salary day filter ─────────────────────────────────────────────────
    # Keep only dates where the calendar day matches the selected contribution day.
    # Because we're already working with actual NAV dates (holidays already shifted
    # to the next trading day by get_next_nav_fast), we compare against the
    # ORIGINAL target day, not the snapped date.
    # Strategy: for each month in range, generate the target date (salary_day),
    # snap it to the next available NAV date, and include that snapped date.
    if salary_day is not None:
        salary_dates = _build_salary_date_candidates(
            nav_dates, nav_vals,
            snapped_start, max_start,
            salary_day,
        )
        # Filter start_candidates to only those that appear in salary_dates
        salary_set = set(salary_dates)
        start_candidates = start_candidates[start_candidates.isin(salary_set)].reset_index(drop=True)

    results = []
    n = len(start_candidates)
    if n == 0:
        return pd.DataFrame()

    for i, start_date in enumerate(start_candidates, 1):
        cashflows    = []
        invest_dates = []
        units        = 0.0

        first_nav_date, first_nav_val = get_next_nav_fast(nav_dates, nav_vals, start_date)
        if first_nav_date is None:
            continue
        units += sip_amount / first_nav_val
        cashflows.append(-sip_amount)
        invest_dates.append(first_nav_date)

        for m in range(1, months_target):
            scheduled = start_date + relativedelta(months=m)
            nav_date, nav_val = get_next_nav_fast(nav_dates, nav_vals, scheduled)
            if nav_date is None:
                break
            units += sip_amount / nav_val
            cashflows.append(-sip_amount)
            invest_dates.append(nav_date)

        if len(cashflows) != months_target:
            continue

        last_date = invest_dates[-1]
        redeem_date, redeem_nav = get_next_nav_fast(
            nav_dates, nav_vals, last_date + relativedelta(days=1)
        )
        if redeem_date is None:
            continue

        final_value = units * redeem_nav
        cashflows.append(final_value)
        invest_dates.append(redeem_date)

        irr_val = xirr(cashflows, invest_dates)
        if np.isnan(irr_val):
            continue

        results.append({
            'Start Date':      start_date.date(),
            'End Date':        last_date.date(),
            'Redemption Date': redeem_date.date(),
            'Instalments':     months_target,
            'XIRR %':          round(irr_val * 100, 2),
            'Final Value':     round(final_value, 2),
        })

        if on_progress and i % PROGRESS_UPDATE_INTERVAL == 0:
            on_progress(i / n)

    if on_progress:
        on_progress(1.0)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values('Start Date').reset_index(drop=True)


def _build_salary_date_candidates(
    nav_dates: np.ndarray,
    nav_vals: np.ndarray,
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
    salary_day: int,
) -> List[pd.Timestamp]:
    """
    Build the list of NAV dates that correspond to the salary contribution day
    within the given date range.

    For each month in [range_start, range_end], construct the target date
    (year, month, salary_day) — clamped to the last day of the month if the
    month is shorter — and snap forward to the next available NAV date.
    """
    candidates = []
    cursor = pd.Timestamp(range_start.year, range_start.month, 1)
    end_ts = range_end

    while cursor <= end_ts:
        # Clamp salary_day to the actual last day of the month
        import calendar
        last_day = calendar.monthrange(cursor.year, cursor.month)[1]
        day = min(salary_day, last_day)
        target = pd.Timestamp(cursor.year, cursor.month, day)

        if target >= range_start:
            snapped, _ = get_next_nav_fast(nav_dates, nav_vals, target)
            if snapped is not None and snapped <= end_ts:
                candidates.append(snapped)

        cursor = cursor + relativedelta(months=1)

    return candidates


# ══════════════════════════════════════════════════════════════════════════════
# ROLLING LUMPSUM (new for NPS)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_all_possible_rolling_lumpsum(
    nav_df_json: str,
    years: int,
    range_start: pd.Timestamp,
    range_end: pd.Timestamp,
    lumpsum_amount: float,
    on_progress=None,
) -> pd.DataFrame:
    """
    Calculate rolling lumpsum returns for all possible start dates.

    For each start date, a single investment of lumpsum_amount is made,
    held for exactly `years` years, then redeemed.  XIRR is computed from
    two cashflows: outflow on invest date, inflow on redeem date.

    Args:
        nav_df_json:    NAV DataFrame serialised as JSON.
        years:          Holding period in years.
        range_start:    Earliest possible investment date.
        range_end:      Latest possible investment date.
        lumpsum_amount: One-time investment amount in rupees.
        on_progress:    Optional progress callback(float 0–1).

    Returns:
        DataFrame with: Start Date, End Date, Redemption Date, XIRR %, Final Value.
    """
    nav_df = pd.read_json(nav_df_json)
    nav_df['date'] = pd.to_datetime(nav_df['date'])

    if nav_df.empty:
        return pd.DataFrame()

    nav_df = nav_df.sort_values('date').reset_index(drop=True)
    nav_dates, nav_vals = build_nav_arrays(nav_df)

    snapped_start, _ = get_next_nav_fast(nav_dates, nav_vals, range_start)
    if snapped_start is None:
        return pd.DataFrame()

    holding_days = int(years * DAYS_PER_YEAR)
    max_start = range_end - relativedelta(years=years)

    start_candidates = nav_df[
        (nav_df['date'] >= snapped_start) &
        (nav_df['date'] <= max_start)
    ]['date'].reset_index(drop=True)

    results = []
    n = len(start_candidates)
    if n == 0:
        return pd.DataFrame()

    for i, start_date in enumerate(start_candidates, 1):
        invest_date, invest_nav = get_next_nav_fast(nav_dates, nav_vals, start_date)
        if invest_date is None:
            continue

        units = lumpsum_amount / invest_nav

        # Redeem after holding period
        redeem_target = invest_date + relativedelta(years=years)
        redeem_date, redeem_nav = get_next_nav_fast(nav_dates, nav_vals, redeem_target)
        if redeem_date is None:
            continue

        final_value = units * redeem_nav
        irr_val = xirr(
            [-lumpsum_amount, final_value],
            [invest_date, redeem_date],
        )
        if np.isnan(irr_val):
            continue

        results.append({
            'Start Date':      invest_date.date(),
            'End Date':        redeem_date.date(),
            'Redemption Date': redeem_date.date(),
            'XIRR %':          round(irr_val * 100, 2),
            'Final Value':     round(final_value, 2),
        })

        if on_progress and i % PROGRESS_UPDATE_INTERVAL == 0:
            on_progress(i / n)

    if on_progress:
        on_progress(1.0)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values('Start Date').reset_index(drop=True)
