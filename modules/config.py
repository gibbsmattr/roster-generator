"""
Configuration settings for the Staff Roster Generator.

This is the primary file to edit when adapting this tool for a new organization.
Update shift definitions, base mappings, staff conflicts, and UI settings here.
"""

# ---------------------------------------------------------------------------
# SHIFT DEFINITIONS
# Each shift needs: rank (priority order), start_time, end_time (HHMM format)
# Lower rank = higher priority shift to staff
# ---------------------------------------------------------------------------

DAY_SHIFTS = {
    "D7B":  {"rank": 1, "start_time": "0700", "end_time": "1900"},
    "D7P":  {"rank": 2, "start_time": "0700", "end_time": "1900"},
    "D9L":  {"rank": 3, "start_time": "0900", "end_time": "2100"},
    "D11M": {"rank": 4, "start_time": "1100", "end_time": "2300"},
    "D11H": {"rank": 5, "start_time": "1100", "end_time": "2300"},
    "MG":   {"rank": 6, "start_time": "1100", "end_time": "2300"},
    "GR":   {"rank": 7, "start_time": "0700", "end_time": "1900"},
    "LG":   {"rank": 8, "start_time": "0900", "end_time": "2100"},
    "PG":   {"rank": 9, "start_time": "0700", "end_time": "1900"},
}

NIGHT_SHIFTS = {
    "N7B": {"rank": 1, "start_time": "1900", "end_time": "0700"},
    "N7P": {"rank": 2, "start_time": "1900", "end_time": "0700"},
    "N9L": {"rank": 3, "start_time": "2100", "end_time": "0900"},
    "NG":  {"rank": 4, "start_time": "1900", "end_time": "0700"},
    "NP":  {"rank": 5, "start_time": "1900", "end_time": "0700"},
}

# Combined shift reference (used for rest calculations)
ALL_SHIFTS = {**DAY_SHIFTS, **NIGHT_SHIFTS}

# ---------------------------------------------------------------------------
# BASE-TO-SHIFT MAPPINGS
# Staff preferences are stored per base; each base maps to one or more shifts.
# Column headers in the Excel file must match the keys here exactly.
# ---------------------------------------------------------------------------
BASE_TO_SHIFTS = {
    "DAY_KMHT": ["D11H"],
    "DAY_KLWM": ["D9L", "LG"],
    "DAY_KBED": ["D7B", "GR"],
    "DAY_1B9":  ["D11M", "MG"],
    "DAY_KPYM": ["D7P", "PG"],
    "NIGHT_KLWM": ["N9L"],
    "NIGHT_KBED": ["N7B", "NG"],
    "NIGHT_KPYM": ["N7P", "NP"],
}

# ---------------------------------------------------------------------------
# REST REQUIREMENTS (hours)
# ---------------------------------------------------------------------------
STANDARD_REST_HOURS = 12   # Default required rest between shifts
REDUCED_REST_HOURS  = 10   # Allowed rest for staff flagged "Reduced Rest OK"

# ---------------------------------------------------------------------------
# STAFF CONFLICT RULES
# Pairs of staff who cannot work the same shift simultaneously.
# ---------------------------------------------------------------------------
STAFF_CONFLICTS = [
    ("Phillips K.", "Phillips R."),
    ("Boomhower",   "King"),
    ("King",        "Holst"),
]

# ---------------------------------------------------------------------------
# STAFF SHIFT RESTRICTIONS
# Map a staff name to a list of shifts they are ALLOWED to work.
# Leave empty to apply no restrictions.
# ---------------------------------------------------------------------------
STAFF_SHIFT_RESTRICTIONS: dict = {
    # Example: "Smith J.": ["D7B", "D7P"]
}

# ---------------------------------------------------------------------------
# UI SETTINGS
# ---------------------------------------------------------------------------
ORG_NAME     = "Staff Roster Generator"   # Displayed in the page title and header
PAGE_LAYOUT  = "wide"                     # "wide" or "centered"
PAGE_ICON    = "🚑"                       # Browser tab icon

# ---------------------------------------------------------------------------
# GITHUB PREFERENCES FILE
# Set this to the raw URL of your preferences .xlsx file on GitHub.
# Format: https://raw.githubusercontent.com/USERNAME/REPO/main/filename.xlsx
# Set to None to disable auto-loading (manual upload only).
# ---------------------------------------------------------------------------
GITHUB_PREFS_URL = None   # e.g. "https://raw.githubusercontent.com/yourname/roster/main/Preferences.xlsx"
