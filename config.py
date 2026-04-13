"""
Configuration file for NPS Rolling Returns application.
All constants and configuration parameters are defined here.
"""

import tempfile

# ══════════════════════════════════════════════════════════════════════════════
# XIRR CALCULATION CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
MAX_XIRR_ITERATIONS = 150       # Maximum Newton-Raphson iterations for XIRR convergence
XIRR_TOLERANCE = 1e-10          # Convergence threshold for XIRR calculation
XIRR_INITIAL_RATE = 0.08        # Starting guess for XIRR (8% annual return)
XIRR_VALIDATION_TOLERANCE = 1e-6  # Final validation threshold relative to redemption value

# ══════════════════════════════════════════════════════════════════════════════
# CACHE SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
CACHE_EXPIRY_DAYS = 1           # NAV cache validity in days (refresh daily)
CACHE_DIR = tempfile.gettempdir()  # Directory for cache files

# ══════════════════════════════════════════════════════════════════════════════
# API SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
NAV_API_TIMEOUT = 15            # Timeout for NAV API calls in seconds
MAX_API_RETRIES = 3             # Maximum retry attempts for failed API calls
RETRY_DELAY_SECONDS = 1.5       # Delay between retry attempts
SCHEMES_API_URL   = "https://npsnav.in/api/schemes"           # All NPS schemes list
HISTORICAL_API_URL = "https://npsnav.in/api/historical"       # Historical NAV per scheme

# ══════════════════════════════════════════════════════════════════════════════
# DATA VALIDATION
# ══════════════════════════════════════════════════════════════════════════════
MIN_VALID_PERIODS = 50          # Minimum rolling periods required for statistical validity
DAYS_PER_YEAR = 365.25          # Average days per year (accounting for leap years)

# ══════════════════════════════════════════════════════════════════════════════
# UI SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
PROGRESS_UPDATE_INTERVAL = 50   # Update progress bar every N iterations

# SIP Amount Limits
MIN_SIP_AMOUNT = 500            # Minimum SIP amount in rupees
MAX_SIP_AMOUNT = 100_000        # Maximum SIP amount in rupees
DEFAULT_SIP_AMOUNT = 1000       # Default SIP amount in rupees

# Lumpsum Amount Limits
MIN_LUMPSUM_AMOUNT = 1_000      # Minimum lumpsum amount in rupees
MAX_LUMPSUM_AMOUNT = 10_000_000 # Maximum lumpsum amount in rupees
DEFAULT_LUMPSUM_AMOUNT = 10_000 # Default lumpsum amount in rupees

# ══════════════════════════════════════════════════════════════════════════════
# CURRENCY FORMATTING
# ══════════════════════════════════════════════════════════════════════════════
CRORE_THRESHOLD = 10_000_000    # Format as crores above this value (1 Cr)
LAKH_THRESHOLD = 100_000        # Format as lakhs above this value (1 L)

# ══════════════════════════════════════════════════════════════════════════════
# ROLLING PERIOD OPTIONS
# ══════════════════════════════════════════════════════════════════════════════
ROLLING_PERIOD_OPTIONS = [1, 2, 3, 5, 7, 10]  # Available rolling period years

# ══════════════════════════════════════════════════════════════════════════════
# RETURN DISTRIBUTION BINS
# ══════════════════════════════════════════════════════════════════════════════
RETURN_BINS = [
    (float('-inf'), 0, '< 0%'),
    (0, 5, '0–5%'),
    (5, 10, '5–10%'),
    (10, 15, '10–15%'),
    (15, 20, '15–20%'),
    (20, float('inf'), '> 20%'),
]

# ══════════════════════════════════════════════════════════════════════════════
# COMPARE MODE
# ══════════════════════════════════════════════════════════════════════════════
MAX_COMPARE_FUNDS = 3           # Maximum funds in compare mode
COMPARE_COLORS = ['#4f83cc', '#e05c5c', '#4caf7d']  # Line colors per fund slot

# ══════════════════════════════════════════════════════════════════════════════
# NPS SPECIFIC MESSAGES
# ══════════════════════════════════════════════════════════════════════════════
MSF_WARNING_TEXT = (
    "This scheme was launched in October 2025. Limited historical data available — "
    "rolling return results may not be reliable."
)
SALARY_DATE_MESSAGE = (
    "Returns are calculated only for SIP windows starting on the selected contribution "
    "day each month. If that date falls on a holiday or non-trading day, the next "
    "available NAV date is used. This reflects a more realistic return scenario for "
    "salaried NPS subscribers."
)

# ══════════════════════════════════════════════════════════════════════════════
# APP METADATA
# ══════════════════════════════════════════════════════════════════════════════
APP_TITLE = "NPS ROLLING RETURNS CALCULATOR"
APP_ICON = "📈"
CREATOR_NAME = "Nijeeth Muniyandi"
CREATOR_EMAIL = "nijeeth91@gmail.com"
DATA_SOURCE_NAME = "npsnav.in"
DATA_SOURCE_URL = "https://npsnav.in"
