"""
API interaction module for NPS Rolling Returns.
Fetches scheme list and historical NAV data from npsnav.in.

npsnav.in wraps all responses in {"data": [...], "metadata": {...}}.
The _unwrap() helper extracts the list before any further processing.
"""

import re
import os
import json
import time
from io import StringIO
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


# ============================================================
# BROWSER HEADERS  (stops npsnav.in from blocking the bot)
# ============================================================

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


# ============================================================
# ENVELOPE UNWRAPPER
# ============================================================

def _unwrap(resp):
    """
    npsnav.in always returns {"data": [...], "metadata": {...}}.
    Extract the list under "data"; fall back gracefully if structure differs.
    """
    if isinstance(resp, dict):
        return resp.get("data", [])
    if isinstance(resp, list):
        return resp
    return []


# ============================================================
# SCHEME NAME PARSER
# ============================================================

_SCHEME_TYPE_PATTERNS = [
    r'NPS\s+LITE',
    r'NPS\s+VATSALYA',
    r'VATSALYA',
    r'MSF',
    r'CENTRAL\s+GOVT',
    r'STATE\s+GOVT',
    r'CORPORATE\s+CG',
    r'CORPORATE\s+OC',
    r'SCHEME\s*[-]?\s*E',
    r'SCHEME\s*[-]?\s*C',
    r'SCHEME\s*[-]?\s*G',
    r'SCHEME\s*[-]?\s*D',
]

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
    """Parse a full NPS scheme name into tier, scheme_type, and pfm."""
    s = name.strip().upper()

    # 1. Strip Tier
    tier = None
    for t in ['TIER II', 'TIER I']:
        m = re.search(r'\b' + t + r'\b', s)
        if m:
            tier = t
            s = s[:m.start()].strip().rstrip('- ').strip()
            break

    if tier is None:
        if re.search(r'NPS\s+LITE', s):
            tier = 'TIER I'
        elif re.search(r'VATSALYA', s):
            tier = 'VATSALYA'
        else:
            tier = 'TIER I'

    # 2. Find scheme type
    scheme_type = None
    type_match_start = type_match_end = None

    for pattern in _SCHEME_TYPE_PATTERNS:
        m = re.search(pattern, s)
        if m:
            raw = re.sub(r'\s+', ' ', m.group().strip())
            raw = re.sub(r'SCHEME\s*[-]?\s*([ECGD])', r'SCHEME \1', raw).strip()
            for key, canonical in _CANONICAL_TYPE.items():
                if key in raw:
                    scheme_type = canonical
                    break
            if scheme_type is None:
                scheme_type = raw
            type_match_start = m.start()
            type_match_end   = m.end()
            break

    if scheme_type is None:
        scheme_type = 'OTHER'
        type_match_start = type_match_end = len(s)

    # 3. Extract PFM
    pfm_raw = s[:type_match_start].strip().rstrip('- ').strip()

    # For prefix-type schemes (NPS LITE, VATSALYA, MSF) the type token sits at
    # the very start so pfm_raw is empty -- PFM actually comes AFTER the token.
    if not pfm_raw and type_match_end < len(s):
        after = s[type_match_end:].strip().lstrip('- ').strip()
        after = re.sub(r'\s*[-]\s*SCHEME\s*[-]?\s*[ECGD].*$', '', after)
        after = re.sub(r'\bSCHEME\s*[-]?\s*[ECGD].*$',        '', after)
        pfm_raw = after.strip().rstrip('- ').strip()

    pfm_raw = re.sub(r'\bPENSION\s+FUND\b', '', pfm_raw)
    pfm_raw = re.sub(r'\bFUND\b',            '', pfm_raw)
    pfm_raw = re.sub(r'\bSCHEME\b',          '', pfm_raw)
    for suffix in _PFM_STRIP:
        pfm_raw = re.sub(suffix, " ", pfm_raw)

    pfm = re.sub(r'\s+', ' ', pfm_raw).strip().rstrip('-').strip()
    if not pfm:
        pfm = 'UNKNOWN'

    return {'tier': tier, 'scheme_type': scheme_type, 'pfm': pfm}


# ============================================================
# DROPDOWN DATA BUILDER
# ============================================================

def build_dropdown_options(schemes: List[Tuple[str, str]]) -> Dict:
    """Parse all schemes and build nested dict for cascading dropdowns."""
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

    standard_tiers = ['TIER I', 'TIER II']
    by_tier: Dict[str, Dict[str, List]] = {}

    for entry in all_parsed:
        t = entry['tier']
        if t not in standard_tiers:
            t = 'TIER I'
        st = entry['scheme_type']
        by_tier.setdefault(t, {}).setdefault(st, [])
        by_tier[t][st].append((entry['code'], entry['name'], entry['pfm']))

    for t in by_tier:
        for st in by_tier[t]:
            by_tier[t][st].sort(key=lambda x: x[2])
        by_tier[t] = dict(sorted(by_tier[t].items()))

    tiers = [t for t in standard_tiers if t in by_tier]

    return {'all_parsed': all_parsed, 'tiers': tiers, 'by_tier': by_tier}


def get_scheme_types_for_tier(dropdown_data: Dict, tier: str) -> List[str]:
    return list(dropdown_data['by_tier'].get(tier, {}).keys())


def get_pfms_for_tier_and_type(
    dropdown_data: Dict, tier: str, scheme_type: str
) -> List[str]:
    entries = dropdown_data['by_tier'].get(tier, {}).get(scheme_type, [])
    return sorted(set(e[2] for e in entries))


def get_scheme_code(
    dropdown_data: Dict, tier: str, scheme_type: str, pfm: str
) -> Optional[Tuple[str, str]]:
    entries = dropdown_data['by_tier'].get(tier, {}).get(scheme_type, [])
    for code, name, entry_pfm in entries:
        if entry_pfm == pfm:
            return code, name
    return None, None


# ============================================================
# SCHEME LIST FETCH
# ============================================================

def _parse_schemes_data(data: list) -> List[Tuple[str, str]]:
    """
    data is the already-unwrapped list (not the full API envelope).
    Handles: [["SM001001", "SBI ..."], ...] and [{"schemeCode": ..., "schemeName": ...}, ...]
    """
    if not data or not isinstance(data, list):
        return []

    first = data[0]

    if isinstance(first, (list, tuple)):
        return [
            (str(item[0]).strip(), str(item[1]).strip())
            for item in data
            if len(item) >= 2
        ]

    if isinstance(first, dict):
        code_keys = ["schemeCode", "code", "scheme_code", "SchemeCode", "id", "Scheme Code"]
        name_keys = ["schemeName", "name", "scheme_name", "SchemeName", "description", "Scheme Name"]
        ck = next((k for k in code_keys if k in first), None)
        nk = next((k for k in name_keys if k in first), None)
        if ck and nk:
            return [(str(item[ck]).strip(), str(item[nk]).strip()) for item in data]

    return []


@st.cache_data(show_spinner=False, ttl=86400)
def _fetch_schemes_cached() -> List[Tuple[str, str]]:
    """
    Internal cached function -- always returns a plain list, never a tuple,
    so @st.cache_data type stays stable across deploys.
    """
    cache_file = os.path.join(CACHE_DIR, "nps_all_schemes.json")

    for attempt in range(MAX_API_RETRIES):
        try:
            r = requests.get(SCHEMES_API_URL, headers=_HEADERS, timeout=NAV_API_TIMEOUT)
            r.raise_for_status()
            resp = r.json()
            data = _unwrap(resp)
            schemes = _parse_schemes_data(data)
            if schemes:
                try:
                    with open(cache_file, "w") as fh:
                        json.dump(schemes, fh)
                except Exception:
                    pass
                return schemes
        except Exception:
            pass

        if attempt < MAX_API_RETRIES - 1:
            time.sleep(2 ** attempt)

    # API failed -- try on-disk cache
    try:
        if os.path.exists(cache_file):
            with open(cache_file) as fh:
                disk = json.load(fh)
            schemes = _parse_schemes_data(disk)
            if schemes:
                return schemes
    except Exception:
        pass

    return []


def fetch_all_schemes() -> Tuple[List[Tuple[str, str]], str]:
    """
    Public wrapper (NOT cached). Returns (schemes, error_message).
    error_message is "" on success.
    Runs a fresh diagnostic request when the cache returns empty.
    """
    try:
        schemes = _fetch_schemes_cached()
        if schemes:
            return schemes, ""

        # Diagnostic: find out WHY the API returned nothing
        try:
            r = requests.get(SCHEMES_API_URL, headers=_HEADERS, timeout=NAV_API_TIMEOUT)
            if r.status_code != 200:
                return [], "npsnav.in returned HTTP {}.".format(r.status_code)
            resp = r.json()
            data = _unwrap(resp)
            if not data:
                return [], "npsnav.in returned an empty data list. Raw: {}".format(str(resp)[:300])
            schemes = _parse_schemes_data(data)
            if schemes:
                return schemes, ""
            return [], "Format not recognised. First item: {}".format(str(data[0])[:200])
        except requests.exceptions.ConnectionError:
            return [], "Cannot reach npsnav.in -- check your internet connection."
        except requests.exceptions.Timeout:
            return [], "npsnav.in did not respond in time (timeout)."
        except Exception as e:
            return [], "Error contacting npsnav.in: {}: {}".format(type(e).__name__, e)

    except Exception as e:
        return [], "Unexpected error: {}: {}".format(type(e).__name__, e)


# ============================================================
# HISTORICAL NAV
# ============================================================

@st.cache_data(show_spinner=False)
def fetch_nav(scheme_code: str) -> pd.DataFrame:
    """
    Fetch historical NAV for one NPS scheme from npsnav.in.
    Response format: {"data": [{"date": "DD-MM-YYYY", "nav": float}, ...], ...}
    Returns DataFrame with columns [date, nav]. Empty DF on failure.
    """
    scheme_code = str(scheme_code).strip()
    cache_file = os.path.join(CACHE_DIR, "nps_nav_{}.csv".format(scheme_code))

    # Use on-disk cache if fresh
    if os.path.exists(cache_file):
        age_days = (
            datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
        ).days
        if age_days < CACHE_EXPIRY_DAYS:
            try:
                return pd.read_csv(cache_file, parse_dates=['date'])
            except Exception:
                pass
        try:
            os.remove(cache_file)
        except Exception:
            pass

    url = "{}/{}".format(HISTORICAL_API_URL, scheme_code)

    raw = None
    for attempt in range(MAX_API_RETRIES):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=NAV_API_TIMEOUT)
            r.raise_for_status()
            resp = r.json()
            raw = _unwrap(resp)
            break
        except Exception:
            if attempt < MAX_API_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                return pd.DataFrame()

    if not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    if df.empty or 'date' not in df.columns or 'nav' not in df.columns:
        return pd.DataFrame()

    df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
    df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
    df = df.dropna(subset=['date', 'nav']).sort_values('date').reset_index(drop=True)

    if not df.empty:
        try:
            df.to_csv(cache_file, index=False)
        except Exception:
            pass

    return df
