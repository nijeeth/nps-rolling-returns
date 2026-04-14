"""
API interaction module for NPS Rolling Returns.
Fetches scheme list and historical NAV data from npsnav.in.
Handles scheme name parsing for the cascading Tier → Scheme Type → PFM dropdowns.
"""

import re
import os
import json
import time
import pandas as pd
import requests
import streamlit as st
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from config import (
    CACHE_DIR,
    CACHE_EXPIRY_DAYS,
    NAV_API_TIMEOUT,
    MAX_API_RETRIES,
    RETRY_DELAY_SECONDS,
    SCHEMES_API_URL,
    HISTORICAL_API_URL,
)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEME NAME PARSER
# ══════════════════════════════════════════════════════════════════════════════

# Scheme type patterns — more specific / longer patterns first
_SCHEME_TYPE_PATTERNS = [
    r'NPS\s+LITE',
    r'NPS\s+VATSALYA',
    r'VATSALYA',
    r'MSF',
    r'CENTRAL\s+GOVT',
    r'STATE\s+GOVT',
    r'CORPORATE\s+CG',
    r'CORPORATE\s+OC',
    r'SCHEME\s*[-–]?\s*E',
    r'SCHEME\s*[-–]?\s*C',
    r'SCHEME\s*[-–]?\s*G',
    r'SCHEME\s*[-–]?\s*D',
]

# Canonical display name for each type
_CANONICAL_TYPE = {
    'NPS LITE':     'NPS LITE',
    'NPS VATSALYA': 'VATSALYA',
    'VATSALYA':     'VATSALYA',
    'MSF':          'MSF',
    'CENTRAL GOVT': 'CENTRAL GOVT',
    'STATE GOVT':   'STATE GOVT',
    'CORPORATE CG': 'CORPORATE CG',
    'CORPORATE OC': 'CORPORATE OC',
    'SCHEME E':     'SCHEME E',
    'SCHEME C':     'SCHEME C',
    'SCHEME G':     'SCHEME G',
    'SCHEME D':     'SCHEME D',
}

# Suffixes to strip from PFM name after removing "PENSION FUND"
_PFM_STRIP = [
    r'\bRETIREMENT\s+SOLUTIONS\b',
    r'\bSUN\s+LIFE\b',
    r'\bPRUDENTIAL\b',
    r'\bPRU\b',
    r'\bMAHINDRA\b',
    r'\bINSURANCE\b',
    r'\bLIFE\b',
]


def parse_scheme_name(name: str) -> Dict[str, str]:
    """
    Parse a full NPS scheme name into its components.

    Args:
        name: Full scheme name e.g. "HDFC PENSION FUND SCHEME E - TIER I"

    Returns:
        dict with keys: tier, scheme_type, pfm
        e.g. {'tier': 'TIER I', 'scheme_type': 'SCHEME E', 'pfm': 'HDFC'}
    """
    s = name.strip().upper()

    # ── 1. Extract Tier (check TIER II before TIER I to avoid partial match) ──
    tier = None
    for t in ['TIER II', 'TIER I']:
        m = re.search(r'\b' + t + r'\b', s)
        if m:
            tier = t
            s = s[:m.start()].strip().rstrip('-– ').strip()
            break

    if tier is None:
        if re.search(r'NPS\s+LITE', s):
            tier = 'TIER I'
        elif re.search(r'VATSALYA', s):
            tier = 'VATSALYA'
        else:
            tier = 'TIER I'

    # ── 2. Find scheme type ────────────────────────────────────────────────
    scheme_type = None
    type_match_start = None

    for pattern in _SCHEME_TYPE_PATTERNS:
        m = re.search(pattern, s)
        if m:
            raw = re.sub(r'\s+', ' ', m.group().strip())
            # Normalise dashes: "SCHEME - E" → "SCHEME E"
            raw = re.sub(r'SCHEME\s*[-–]?\s*([ECGD])', r'SCHEME \1', raw).strip()
            for key, canonical in _CANONICAL_TYPE.items():
                if key in raw:
                    scheme_type = canonical
                    break
            if scheme_type is None:
                scheme_type = raw
            type_match_start = m.start()
            break

    if scheme_type is None:
        scheme_type = 'OTHER'
        type_match_start = len(s)

    # ── 3. Extract PFM from the part before the scheme type ───────────────
    pfm_raw = s[:type_match_start].strip().rstrip('-– ').strip()

    # Special case: NPS LITE has "NPS LITE - SBI PENSION FUND - SCHEME ..."
    if scheme_type == 'NPS LITE':
        m2 = re.search(r'NPS\s+LITE\s*[-–]\s*(.+?)(?:\s*[-–]\s*SCHEME.*)?$', pfm_raw + ' ' + scheme_type)
        if m2:
            pfm_raw = m2.group(1).strip()

    # Remove "PENSION FUND" and standalone "FUND"
    pfm_raw = re.sub(r'\bPENSION\s+FUND\b', '', pfm_raw)
    pfm_raw = re.sub(r'\bFUND\b', '', pfm_raw)

    # Strip known filler words
    for suffix in _PFM_STRIP:
        pfm_raw = re.sub(suffix, ' ', pfm_raw)

    pfm = re.sub(r'\s+', ' ', pfm_raw).strip()
    if not pfm:
        pfm = 'UNKNOWN'

    return {'tier': tier, 'scheme_type': scheme_type, 'pfm': pfm}


# ══════════════════════════════════════════════════════════════════════════════
# DROPDOWN DATA BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_dropdown_options(schemes: List[Tuple[str, str]]) -> Dict:
    """
    Parse all schemes and build data structures for the cascading dropdowns.

    Args:
        schemes: List of (scheme_code, scheme_name) tuples from the API

    Returns:
        dict with:
          'all_parsed'   — list of {code, name, tier, scheme_type, pfm}
          'tiers'        — sorted list of unique tiers (TIER I, TIER II only)
          'by_tier'      — {tier: {scheme_type: [(code, name, pfm), ...]}}
    """
    all_parsed = []
    for code, name in schemes:
        parsed = parse_scheme_name(name)
        all_parsed.append({
            'code': code,
            'name': name,
            'tier': parsed['tier'],
            'scheme_type': parsed['scheme_type'],
            'pfm': parsed['pfm'],
        })

    # Only TIER I and TIER II in the main dropdowns
    # VATSALYA etc. are edge cases we'll include under TIER I for now
    standard_tiers = ['TIER I', 'TIER II']

    # Build nested dict: tier → scheme_type → list of (code, name, pfm)
    by_tier: Dict[str, Dict[str, List]] = {}
    for entry in all_parsed:
        t = entry['tier']
        # Map non-standard tiers into TIER I
        if t not in standard_tiers:
            t = 'TIER I'
        st = entry['scheme_type']
        by_tier.setdefault(t, {}).setdefault(st, [])
        by_tier[t][st].append((entry['code'], entry['name'], entry['pfm']))

    # Sort scheme types and PFMs within each tier
    for t in by_tier:
        for st in by_tier[t]:
            by_tier[t][st].sort(key=lambda x: x[2])  # sort by pfm name
        by_tier[t] = dict(sorted(by_tier[t].items()))  # sort scheme types

    tiers = [t for t in standard_tiers if t in by_tier]

    return {
        'all_parsed': all_parsed,
        'tiers': tiers,
        'by_tier': by_tier,
    }


def get_scheme_types_for_tier(dropdown_data: Dict, tier: str) -> List[str]:
    """Return sorted list of scheme types available for the given tier."""
    return list(dropdown_data['by_tier'].get(tier, {}).keys())


def get_pfms_for_tier_and_type(dropdown_data: Dict, tier: str, scheme_type: str) -> List[str]:
    """Return sorted list of PFM short names for tier + scheme type combination."""
    entries = dropdown_data['by_tier'].get(tier, {}).get(scheme_type, [])
    return sorted(set(e[2] for e in entries))


def get_scheme_code(dropdown_data: Dict, tier: str, scheme_type: str, pfm: str) -> Optional[Tuple[str, str]]:
    """
    Look up (code, full_name) for the selected tier + scheme_type + pfm.

    Returns:
        (scheme_code, full_scheme_name) tuple, or (None, None) if not found.
    """
    entries = dropdown_data['by_tier'].get(tier, {}).get(scheme_type, [])
    for code, name, entry_pfm in entries:
        if entry_pfm == pfm:
            return code, name
    return None, None


# ══════════════════════════════════════════════════════════════════════════════
# API CALLS
# ══════════════════════════════════════════════════════════════════════════════

# Browser-like headers so npsnav.in doesn't block the request
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://npsnav.in/",
}


def _parse_schemes_response(data) -> List[Tuple[str, str]]:
    """
    Normalise the API response into a list of (code, name) tuples.
    Handles three shapes the API might return:
      - [[code, name], ...]          — list of 2-element lists
      - [[code, name, ...], ...]     — list with extra fields (take first two)
      - [{"schemeCode": ..., "schemeName": ...}, ...]  — list of dicts
    """
    if not data or not isinstance(data, list):
        return []

    first = data[0]

    if isinstance(first, (list, tuple)):
        return [(str(item[0]).strip(), str(item[1]).strip()) for item in data if len(item) >= 2]

    if isinstance(first, dict):
        # Try common key names
        code_keys = ["schemeCode", "code", "scheme_code", "SchemeCode", "id"]
        name_keys = ["schemeName", "name", "scheme_name", "SchemeName", "description"]
        ck = next((k for k in code_keys if k in first), None)
        nk = next((k for k in name_keys if k in first), None)
        if ck and nk:
            return [(str(item[ck]).strip(), str(item[nk]).strip()) for item in data]

    return []


@st.cache_data(show_spinner=False, ttl=86400)
def _fetch_schemes_cached() -> List[Tuple[str, str]]:
    """
    Internal cached function — always returns a plain list (never a tuple).
    @st.cache_data only wraps this so the return type never changes between deploys.
    Returns empty list on failure; the public wrapper handles error messaging.
    """
    cache_file = os.path.join(CACHE_DIR, "nps_all_schemes.json")

    for attempt in range(MAX_API_RETRIES):
        try:
            r = requests.get(
                SCHEMES_API_URL,
                headers=_HEADERS,
                timeout=NAV_API_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            schemes = _parse_schemes_response(data)
            if schemes:
                try:
                    with open(cache_file, 'w') as fh:
                        json.dump(schemes, fh)
                except Exception:
                    pass
                return schemes
        except Exception:
            pass

        if attempt < MAX_API_RETRIES - 1:
            time.sleep(2 ** attempt)

    # API failed — try on-disk cache
    try:
        if os.path.exists(cache_file):
            with open(cache_file) as fh:
                data = json.load(fh)
            schemes = [(str(item[0]), str(item[1])) for item in data]
            if schemes:
                return schemes
    except Exception:
        pass

    return []


def fetch_all_schemes() -> Tuple[List[Tuple[str, str]], str]:
    """
    Public wrapper around _fetch_schemes_cached().
    NOT decorated with @st.cache_data — returns (schemes, error_message).
    error_message is "" on success, human-readable string on failure.
    """
    try:
        schemes = _fetch_schemes_cached()
        if schemes:
            return schemes, ""

        # Cached function returned empty — run a live diagnostic request
        # (not cached) so we can surface the actual error to the user
        try:
            r = requests.get(SCHEMES_API_URL, headers=_HEADERS, timeout=NAV_API_TIMEOUT)
            if r.status_code != 200:
                return [], f"npsnav.in returned HTTP {r.status_code}."
            data = r.json()
            if not data:
                return [], "npsnav.in returned an empty response."
            return [], (
                f"API response format not recognised. "
                f"First item was: {str(data[0])[:200]}"
            )
        except requests.exceptions.ConnectionError:
            return [], "Cannot reach npsnav.in — check your internet connection."
        except requests.exceptions.Timeout:
            return [], "npsnav.in did not respond in time (timeout)."
        except Exception as e:
            return [], f"Error contacting npsnav.in: {type(e).__name__}: {e}"

    except Exception as e:
        return [], f"Unexpected error loading schemes: {type(e).__name__}: {e}"


@st.cache_data(show_spinner=False)
def fetch_nav(scheme_code: str) -> pd.DataFrame:
    """
    Fetch historical NAV for an NPS scheme from npsnav.in.

    The API returns dates in DD-MM-YYYY format; we convert immediately to
    YYYY-MM-DD so the rest of the app works identically to the MF calculator.

    Args:
        scheme_code: NPS scheme code e.g. "SM008001"

    Returns:
        DataFrame with columns ['date' (datetime), 'nav' (float)], sorted ascending.
        Returns empty DataFrame if fetch fails.
    """
    scheme_code = str(scheme_code).strip()
    cache_file = os.path.join(CACHE_DIR, f"nps_nav_{scheme_code}.csv")

    # Check file cache (avoids hammering the API on reruns)
    if os.path.exists(cache_file):
        age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))).days
        if age_days < CACHE_EXPIRY_DAYS:
            try:
                return pd.read_csv(cache_file, parse_dates=['date'])
            except Exception:
                pass
        try:
            os.remove(cache_file)
        except Exception:
            pass

    url = f"{HISTORICAL_API_URL}/{scheme_code}"

    for attempt in range(MAX_API_RETRIES):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=NAV_API_TIMEOUT)
            r.raise_for_status()
            raw = r.json()
            break
        except Exception:
            if attempt < MAX_API_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                return pd.DataFrame()

    # raw is a list of {"date": "DD-MM-YYYY", "nav": float}
    df = pd.DataFrame(raw)
    if df.empty or 'date' not in df.columns or 'nav' not in df.columns:
        return pd.DataFrame()

    # ── KEY: convert DD-MM-YYYY → datetime immediately ────────────────────
    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
    df['nav']  = pd.to_numeric(df['nav'], errors='coerce')
    df = df.dropna(subset=['date', 'nav']).sort_values('date').reset_index(drop=True)

    if not df.empty:
        try:
            df.to_csv(cache_file, index=False)
        except Exception:
            pass

    return df
