"""
Utility functions for NPS Rolling Returns application.
Includes formatting, validation, charting, and Excel export functions.

Changes vs MF calculator:
  - validate_inputs() — fund code check replaced by scheme_selected check
  - plot_rolling_xirr_compare() — overlapping lines for up to 3 funds
  - build_excel_compare()       — multi-sheet Excel with Summary tab
  - build_excel()               — updated header/attribution for NPS
"""

import calendar
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date
from io import BytesIO
from typing import Optional, List, Dict

from config import (
    CRORE_THRESHOLD,
    LAKH_THRESHOLD,
    MIN_VALID_PERIODS,
    CREATOR_NAME,
    CREATOR_EMAIL,
    DATA_SOURCE_URL,
    DATA_SOURCE_NAME,
    COMPARE_COLORS,
)


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def format_date(dt) -> str:
    """Return DD/MM/YYYY string, or '—' for None."""
    if dt is None:
        return "—"
    if isinstance(dt, pd.Timestamp):
        dt = dt.date()
    return dt.strftime("%d/%m/%Y")


def fmt_inr(v: float) -> str:
    """
    Format a number as Indian Rupees with Lakh/Crore notation.
    Handles negatives with a leading minus sign.
    """
    sign = '-' if v < 0 else ''
    v = int(round(abs(v)))
    if v >= CRORE_THRESHOLD:
        return f'{sign}₹{v/10_000_000:.2f} Cr'
    elif v >= LAKH_THRESHOLD:
        return f'{sign}₹{v/100_000:.2f} L'
    return f'{sign}₹{v:,}'


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def validate_inputs(
    scheme_selected: bool,
    from_date: Optional[date],
    to_date: Optional[date],
    years: int,
    nav_df: Optional[pd.DataFrame] = None,
) -> List[str]:
    """
    Validate all user inputs. Returns a list of error messages (empty = OK).

    Args:
        scheme_selected: True if the user has fully selected Tier+SchemeType+PFM.
        from_date:       Start date of analysis range.
        to_date:         End date of analysis range.
        years:           Rolling period in years.
        nav_df:          NAV DataFrame (optional, for boundary checks).
    """
    errors = []

    if not scheme_selected:
        errors.append("Please select Tier, Scheme Type, and Fund (PFM) to continue.")

    if from_date is None or to_date is None:
        errors.append("Please select both From and To dates.")
        return errors

    if from_date >= to_date:
        errors.append("From date must be before To date.")

    range_months = (to_date.year - from_date.year) * 12 + (to_date.month - from_date.month)
    needed_months = years * 12
    if range_months < needed_months:
        errors.append(
            f"Selected date range is less than the rolling period "
            f"({years} year{'s' if years > 1 else ''}). Please extend the time period."
        )

    if nav_df is not None and not nav_df.empty:
        first_nav = nav_df['date'].min().date()
        last_nav  = nav_df['date'].max().date()

        if from_date < first_nav:
            errors.append(
                f"From date is outside available NAV data. "
                f"Please select a date on or after {format_date(first_nav)}."
            )
        if to_date > last_nav:
            errors.append(
                f"To date is outside available NAV data. "
                f"Please select a date on or before {format_date(last_nav)}."
            )

    return errors


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-FUND CHART
# ══════════════════════════════════════════════════════════════════════════════

def plot_rolling_xirr(df: pd.DataFrame, scheme_name: str, years: int) -> plt.Figure:
    """
    Rolling XIRR chart for a single fund.

    Args:
        df:          DataFrame with 'Start Date' and 'XIRR %' columns.
        scheme_name: Full scheme name (used in title).
        years:       Rolling period in years.
    """
    fig, ax = plt.subplots(figsize=(8, 2.5))
    x = pd.to_datetime(df['Start Date'])
    y = df['XIRR %']

    ax.fill_between(x, y, alpha=0.15, color='steelblue')
    ax.plot(x, y, color='steelblue', linewidth=1.2, label='XIRR %')

    mean_val = y.mean()
    ax.axhline(mean_val, color='darkorange', linewidth=1.4,
               linestyle='--', label=f'Mean: {mean_val:.2f}%')
    ax.axhline(0, color='red', linewidth=0.8, linestyle=':')

    ax.set_title(f'{scheme_name}  |  {years}-Year Rolling XIRR',
                 fontsize=11, fontweight='normal', pad=10)
    ax.set_xlabel('Start Date', fontsize=10)
    ax.set_ylabel('XIRR (%)', fontsize=10)
    ax.tick_params(axis='both', labelsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=30, ha='right')
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# COMPARE CHART (up to 3 funds, overlapping lines)
# ══════════════════════════════════════════════════════════════════════════════

def plot_rolling_xirr_compare(
    fund_results: List[Dict],
    years: int,
) -> plt.Figure:
    """
    Overlapping rolling XIRR chart for up to 3 funds.

    Args:
        fund_results: List of dicts, each with keys:
                        'label' — short PFM name shown in legend
                        'df'    — DataFrame with 'Start Date' and 'XIRR %'
        years:        Rolling period in years.
    """
    fig, ax = plt.subplots(figsize=(9, 3))

    for idx, fund in enumerate(fund_results[:3]):
        color = COMPARE_COLORS[idx]
        label = fund['label']
        df    = fund['df']
        x = pd.to_datetime(df['Start Date'])
        y = df['XIRR %']
        ax.plot(x, y, color=color, linewidth=1.4, label=label, alpha=0.9)
        mean_val = y.mean()
        ax.axhline(mean_val, color=color, linewidth=0.9,
                   linestyle='--', alpha=0.6)

    ax.axhline(0, color='red', linewidth=0.8, linestyle=':')
    ax.set_title(f'{years}-Year Rolling XIRR — Fund Comparison',
                 fontsize=11, fontweight='normal', pad=10)
    ax.set_xlabel('SIP / Lumpsum Start Date', fontsize=10)
    ax.set_ylabel('XIRR (%)', fontsize=10)
    ax.tick_params(axis='both', labelsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=30, ha='right')
    ax.legend(fontsize=9, loc='upper left')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-FUND EXCEL EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def build_excel(
    df_export: pd.DataFrame,
    scheme_name: str,
    years: int,
    from_date: date,
    to_date: date,
    is_sip: bool,
    amount: int,
) -> BytesIO:
    """
    Build an Excel file with rolling returns data for a single NPS scheme.

    Args:
        df_export:   Formatted DataFrame (dates already as DD/MM/YYYY strings).
        scheme_name: Full NPS scheme name.
        years:       Rolling period in years.
        from_date:   Start of analysis range.
        to_date:     End of analysis range.
        is_sip:      True for SIP, False for Lumpsum.
        amount:      Monthly SIP or lumpsum amount in rupees.
    """
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        gen_date = datetime.now().strftime('%d/%m/%Y %H:%M')
        from_str = from_date.strftime('%d/%m/%Y')
        to_str   = to_date.strftime('%d/%m/%Y')
        mode_str = 'SIP' if is_sip else 'Lumpsum'

        df_export.to_excel(writer, index=False,
                           sheet_name='Rolling XIRR', startrow=18)
        wb = writer.book
        ws = writer.sheets['Rolling XIRR']

        def mf(opts): return wb.add_format(opts)

        HDR_COLS = max(len(df_export.columns), 7)
        NC = HDR_COLS - 1

        ws.set_column(0, 0, 20)
        ws.set_column(1, 1, 20)
        ws.set_column(2, 2, 20)
        ws.set_column(3, 3, 14)
        ws.set_column(4, 4, 14)

        fmt_h1      = mf({'bold': True, 'font_size': 14, 'font_color': '#FFFFFF',
                          'bg_color': '#0D47A1', 'valign': 'vcenter', 'border': 0})
        fmt_lbl     = mf({'bold': True, 'font_size': 10, 'font_color': '#0D47A1',
                          'bg_color': '#E3F2FD', 'valign': 'vcenter', 'border': 0})
        fmt_meta    = mf({'bold': True, 'font_size': 10, 'font_color': '#1B5E20',
                          'bg_color': '#E8F5E9', 'valign': 'vcenter', 'text_wrap': True, 'border': 0})
        fmt_creator = mf({'bold': True, 'font_size': 10, 'font_color': '#1B5E20',
                          'bg_color': '#E8F5E9', 'valign': 'vcenter', 'border': 0})
        fmt_thanks  = mf({'font_size': 10, 'font_color': '#880E4F', 'bg_color': '#FCE4EC',
                          'valign': 'vcenter', 'text_wrap': True, 'border': 0})
        fmt_url     = mf({'bold': True, 'font_size': 10, 'font_color': '#880E4F',
                          'underline': 1, 'bg_color': '#FCE4EC', 'valign': 'vcenter', 'border': 0})
        fmt_disc1   = mf({'font_size': 10, 'font_color': '#333333', 'bg_color': '#FFF8E1',
                          'valign': 'vcenter', 'text_wrap': True, 'border': 0})
        fmt_disc2   = mf({'bold': True, 'font_size': 10, 'font_color': '#B71C1C',
                          'bg_color': '#FFCDD2', 'valign': 'vcenter', 'text_wrap': True, 'border': 0})
        fmt_disc3   = mf({'font_size': 10, 'font_color': '#880E4F', 'bg_color': '#FCE4EC',
                          'valign': 'vcenter', 'text_wrap': True, 'border': 0})
        fmt_perf    = mf({'italic': True, 'font_size': 9, 'font_color': '#6A0DAD',
                          'bg_color': '#F3E5F5', 'valign': 'vcenter', 'border': 0})
        fmt_sep     = mf({'bg_color': '#90A4AE', 'border': 0})
        fmt_blank   = mf({'bg_color': '#E3F2FD', 'border': 0})

        ws.merge_range(0, 0, 0, NC,
                       f'{years}-Year {mode_str} Rolling Return — NPS', fmt_h1)
        ws.set_row(0, 26)
        ws.write(1, 0, 'Scheme Name:', fmt_lbl)
        ws.merge_range(1, 1, 1, NC, scheme_name, fmt_meta)
        ws.set_row(1, 20)
        ws.write(2, 0, 'Rolling Years:', fmt_lbl)
        ws.write(2, 1, f'{years} Year(s)', fmt_meta)
        ws.write(2, 2, 'Mode:', fmt_lbl)
        ws.write(2, 3, mode_str, fmt_meta)
        ws.write(2, 4, 'From Date:', fmt_lbl)
        ws.write(2, 5, from_str, fmt_meta)
        ws.write(2, 6 if NC >= 6 else NC, 'To Date:', fmt_lbl)
        if NC >= 7:
            ws.write(2, 7, to_str, fmt_meta)
        for c in range(8, NC + 1): ws.write(2, c, '', fmt_blank)
        ws.set_row(2, 20)

        if is_sip:
            ws.write(3, 0, 'Monthly SIP:', fmt_lbl)
            ws.write(3, 1, f'₹{amount:,}/month', fmt_meta)
            ws.write(3, 2, 'Total Invested:', fmt_lbl)
            ws.write(3, 3, f'₹{amount * years * 12:,}', fmt_meta)
            for c in range(4, NC + 1): ws.write(3, c, '', fmt_blank)
        else:
            ws.write(3, 0, 'Lumpsum Amount:', fmt_lbl)
            ws.write(3, 1, f'₹{amount:,}', fmt_meta)
            for c in range(2, NC + 1): ws.write(3, c, '', fmt_blank)
        ws.set_row(3, 20)

        ws.write(4, 0, 'File Generated:', fmt_lbl)
        ws.write(4, 1, gen_date, fmt_meta)
        for c in range(2, NC + 1): ws.write(4, c, '', fmt_blank)
        ws.set_row(4, 20)

        ws.write(5, 0, 'Created by:', fmt_lbl)
        ws.write(5, 1, CREATOR_NAME, fmt_creator)
        ws.write(5, 3, 'Contact:', fmt_lbl)
        ws.write(5, 4, CREATOR_EMAIL, fmt_meta)
        for c in range(5, NC + 1): ws.write(5, c, '', fmt_blank)
        ws.set_row(5, 22)

        ws.merge_range(6, 0, 6, NC, '', fmt_sep)
        ws.set_row(6, 4)

        ws.write_url(7, 0, DATA_SOURCE_URL, fmt_url,
                     f'Special Thanks: {DATA_SOURCE_NAME}')
        ws.merge_range(7, 1, 7, NC,
                       f'for providing NPS NAV data through their freely accessible API. '
                       f'For personal/educational/non-commercial use only.',
                       fmt_thanks)
        ws.set_row(7, 40)

        ws.merge_range(8, 0, 8, NC, '', fmt_sep)
        ws.set_row(8, 4)
        ws.merge_range(9, 0, 9, NC,
                       'Disclaimer: This tool is a personal project created with AI assistance. '
                       'It may contain inaccuracies or errors. '
                       f'For suggestions/feedback: {CREATOR_EMAIL}', fmt_disc1)
        ws.set_row(9, 55)
        ws.merge_range(10, 0, 10, NC,
                       '⚠ NOT financial advice. NPS returns are subject to market risks. '
                       'Past performance does not guarantee future returns. '
                       'The creator is NOT a SEBI-registered investment advisor. '
                       'Consult a qualified financial advisor before investing.', fmt_disc2)
        ws.set_row(10, 55)
        ws.merge_range(11, 0, 11, NC,
                       '⚠ This tool relies on third-party data which may be delayed or incomplete. '
                       'The creator is NOT responsible for any financial losses or decisions '
                       'resulting from the use of this tool.', fmt_disc3)
        ws.set_row(11, 45)
        ws.merge_range(12, 0, 12, NC, '', fmt_sep)
        ws.set_row(12, 4)
        ws.merge_range(13, 0, 13, NC,
                       '⚠ Past performance does not guarantee future returns.', fmt_perf)
        ws.set_row(13, 18)
        ws.merge_range(14, 0, 14, NC, '', fmt_sep)
        ws.set_row(14, 4)
        ws.merge_range(15, 0, 15, NC, '', fmt_blank)
        ws.set_row(15, 6)
        ws.set_row(16, 16)

    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
# COMPARE-MODE EXCEL EXPORT (multi-sheet)
# ══════════════════════════════════════════════════════════════════════════════

def build_excel_compare(
    fund_results: List[Dict],
    years: int,
    from_date: date,
    to_date: date,
    is_sip: bool,
    amount: int,
) -> BytesIO:
    """
    Build a multi-sheet Excel file for compare mode.

    Args:
        fund_results: List of dicts, each with:
                        'name'  — full scheme name
                        'label' — short PFM label
                        'df'    — DataFrame with rolling return data
        years:        Rolling period in years.
        from_date:    Start of analysis range.
        to_date:      End of analysis range.
        is_sip:       True for SIP, False for Lumpsum.
        amount:       Monthly SIP or lumpsum amount in rupees.

    Sheet layout:
        Summary  — one row per fund with Min/Median/Mean/Max/Std Dev
        Fund 1, Fund 2, Fund 3 — full data tables, full scheme name as row 0 header
    """
    buf = BytesIO()
    gen_date = datetime.now().strftime('%d/%m/%Y %H:%M')
    mode_str = 'SIP' if is_sip else 'Lumpsum'

    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        wb = writer.book

        # ── Formats ─────────────────────────────────────────────────────────
        def mf(opts): return wb.add_format(opts)
        fmt_title   = mf({'bold': True, 'font_size': 13, 'font_color': '#FFFFFF',
                          'bg_color': '#0D47A1', 'align': 'center', 'valign': 'vcenter'})
        fmt_hdr     = mf({'bold': True, 'font_size': 10, 'font_color': '#3730a3',
                          'bg_color': '#e8eaf6', 'align': 'center', 'valign': 'vcenter',
                          'border': 1})
        fmt_fund    = mf({'bold': True, 'font_size': 10, 'font_color': '#1B5E20',
                          'bg_color': '#E8F5E9', 'text_wrap': True, 'valign': 'vcenter'})
        fmt_num     = mf({'num_format': '0.00', 'align': 'center', 'border': 1})
        fmt_worst   = mf({'bold': True, 'num_format': '0.00', 'font_color': '#dc2626',
                          'bg_color': '#fef2f2', 'align': 'center', 'border': 1})
        fmt_best    = mf({'bold': True, 'num_format': '0.00', 'font_color': '#16a34a',
                          'bg_color': '#f0fdf4', 'align': 'center', 'border': 1})
        fmt_scheme  = mf({'bold': True, 'font_size': 11, 'font_color': '#FFFFFF',
                          'bg_color': '#1a237e', 'text_wrap': True, 'valign': 'vcenter'})
        fmt_disc    = mf({'italic': True, 'font_size': 9, 'font_color': '#666666',
                          'text_wrap': True})

        # ── SUMMARY SHEET ────────────────────────────────────────────────────
        ws_sum = wb.add_worksheet('Summary')
        writer.sheets['Summary'] = ws_sum

        cols = ['Fund', 'Min XIRR %', '25th %ile', 'Median', 'Mean', '75th %ile', 'Max XIRR %', 'Std Dev']
        col_widths = [40, 12, 12, 12, 12, 12, 12, 12]
        for c, (col, w) in enumerate(zip(cols, col_widths)):
            ws_sum.set_column(c, c, w)

        ws_sum.merge_range(0, 0, 0, len(cols) - 1,
                           f'NPS Rolling Returns — {years}-Year {mode_str} Comparison | '
                           f'{from_date.strftime("%d/%m/%Y")} to {to_date.strftime("%d/%m/%Y")} | '
                           f'Generated: {gen_date}',
                           fmt_title)
        ws_sum.set_row(0, 26)

        for c, col in enumerate(cols):
            ws_sum.write(1, c, col, fmt_hdr)
        ws_sum.set_row(1, 20)

        for row_idx, fund in enumerate(fund_results):
            df = fund['df']
            x  = df['XIRR %']
            fmts = [fmt_num] * len(cols)
            fmts[1] = fmt_worst   # Min
            fmts[6] = fmt_best    # Max
            ws_sum.write(row_idx + 2, 0, fund['name'], fmt_fund)
            for c, (val, fmt) in enumerate(zip(
                [round(x.min(), 2), round(float(x.quantile(0.25)), 2),
                 round(x.median(), 2), round(x.mean(), 2),
                 round(float(x.quantile(0.75)), 2), round(x.max(), 2),
                 round(x.std(), 2)],
                fmts[1:]
            )):
                ws_sum.write(row_idx + 2, c + 1, val, fmt)
            ws_sum.set_row(row_idx + 2, 18)

        # Disclaimer row
        disc_row = len(fund_results) + 4
        ws_sum.merge_range(disc_row, 0, disc_row, len(cols) - 1,
                           '⚠ NOT financial advice. Past performance does not guarantee future returns. '
                           'For personal/educational use only. Data sourced from npsnav.in.',
                           fmt_disc)
        ws_sum.set_row(disc_row, 30)

        # ── INDIVIDUAL FUND SHEETS ────────────────────────────────────────
        for fund_idx, fund in enumerate(fund_results[:3]):
            sheet_name = f'Fund {fund_idx + 1}'
            df = fund['df'].copy()

            # Format dates
            for col in ['Start Date', 'End Date', 'Redemption Date']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col]).dt.strftime('%d/%m/%Y')

            # Write scheme name as header row, then data starting at row 2
            df.to_excel(writer, index=False, sheet_name=sheet_name, startrow=2)
            ws = writer.sheets[sheet_name]

            ws.merge_range(0, 0, 0, len(df.columns) - 1, fund['name'], fmt_scheme)
            ws.set_row(0, 32)
            ws.set_row(1, 4)  # small spacer row

            # Column widths
            ws.set_column(0, 2, 18)   # date columns
            ws.set_column(3, 3, 12)
            ws.set_column(4, 4, 12)
            if len(df.columns) > 5:
                ws.set_column(5, len(df.columns) - 1, 16)

    buf.seek(0)
    return buf
