"""
Utility functions for shift time calculations and eligibility checks.
"""

import datetime
from modules.config import (
    ALL_SHIFTS, DAY_SHIFTS, NIGHT_SHIFTS,
    STANDARD_REST_HOURS, REDUCED_REST_HOURS,
    STAFF_CONFLICTS, STAFF_SHIFT_RESTRICTIONS,
)


# ---------------------------------------------------------------------------
# Shift code helpers
# ---------------------------------------------------------------------------

def normalize_shift_code(shift_code: str) -> str:
    """
    Strip the trailing 'p' suffix used to denote a dual-role staff member
    functioning as a medic (e.g. 'MGp' → 'MG').
    """
    if shift_code and shift_code.endswith("p"):
        return shift_code[:-1]
    return shift_code


def is_day_shift(shift_code: str) -> bool:
    """Return True if the (possibly 'p'-suffixed) shift code is a day shift."""
    return normalize_shift_code(shift_code) in DAY_SHIFTS


def is_night_shift(shift_code: str) -> bool:
    """Return True if the (possibly 'p'-suffixed) shift code is a night shift."""
    return normalize_shift_code(shift_code) in NIGHT_SHIFTS


# ---------------------------------------------------------------------------
# Rest-requirement logic
# ---------------------------------------------------------------------------

def _hours(time_str: str) -> float:
    """Convert a 'HHMM' string to a floating-point hour value."""
    return int(time_str[:2]) + int(time_str[2:]) / 60


def check_rest_requirements(prior_shift: str, new_shift: str, reduced_rest_ok: bool) -> bool:
    """
    Determine whether sufficient rest exists between a prior shift and the new shift.

    Both shift codes are normalised before lookup.  Returns False if either code
    is unrecognised (to err on the side of caution).
    """
    prior = normalize_shift_code(prior_shift)
    new   = normalize_shift_code(new_shift)

    if prior not in ALL_SHIFTS or new not in ALL_SHIFTS:
        return False

    prior_end   = _hours(ALL_SHIFTS[prior]["end_time"])
    new_start   = _hours(ALL_SHIFTS[new]["start_time"])
    prior_is_day = prior in DAY_SHIFTS

    # Night shifts that end in the morning (e.g. 07:00) are the tricky case.
    if not prior_is_day and prior_end < 12 and new in DAY_SHIFTS:
        # Same-day morning handoff: rest = gap between end of night and start of day.
        rest_hours = new_start - prior_end
    else:
        # Standard cross-day calculation: time from shift end to next start.
        rest_hours = (24 - prior_end) + new_start

    min_rest = REDUCED_REST_HOURS if reduced_rest_ok else STANDARD_REST_HOURS
    return rest_hours >= min_rest


# ---------------------------------------------------------------------------
# Main eligibility check
# ---------------------------------------------------------------------------

def can_staff_work_shift(
    staff_name: str,
    staff_role: str,
    shift: str,
    current_staff: list,
    prior_shifts: dict,
    reduced_rest_ok: bool,
    no_matrix: int,
    balls_full: bool = False,
    current_no_matrix_count: int = 0,
    enforce_no_matrix_rule: bool = True,
) -> tuple[bool, str]:
    """
    Return ``(can_work, reason)`` for a prospective assignment.

    Rules checked (in order):
    1. The shift's role slot for this role is not already filled.
    2. The shift is not already fully staffed (two people).
    3. Prior-shift rest requirements are met.
    4. No staff-conflict pairs share the shift.
    5. Staff-specific shift restrictions are respected.
    6. No-Matrix / BALLS constraints are satisfied.
    7. At least one No-Matrix staff member per shift is ensured (if enforce_no_matrix_rule=True).
    """
    current_roles = [s[1] for s in current_staff]

    # 1. Role slot already filled?
    if staff_role in current_roles:
        return False, f"Role '{staff_role}' already filled on {shift}"

    # 2. Shift fully staffed?
    if len(current_staff) >= 2:
        return False, f"Shift {shift} is already fully staffed"

    # 3. Rest requirements
    if staff_name in prior_shifts:
        prior = prior_shifts[staff_name]
        norm_prior = normalize_shift_code(prior)
        if norm_prior in ALL_SHIFTS:
            if not check_rest_requirements(prior, shift, reduced_rest_ok):
                prior_end   = _hours(ALL_SHIFTS[norm_prior]["end_time"])
                new_start   = _hours(ALL_SHIFTS[shift]["start_time"])
                prior_is_day = norm_prior in DAY_SHIFTS
                if not prior_is_day and prior_end < 12 and shift in DAY_SHIFTS:
                    rest_h = new_start - prior_end
                else:
                    rest_h = (24 - prior_end) + new_start
                min_rest = REDUCED_REST_HOURS if reduced_rest_ok else STANDARD_REST_HOURS
                return False, (
                    f"Insufficient rest ({rest_h:.1f}h) after prior shift {prior} "
                    f"(minimum {min_rest}h required)"
                )

    # 4. Staff conflict pairs
    current_names = [s[0] for s in current_staff]
    for a, b in STAFF_CONFLICTS:
        if (staff_name == a and b in current_names) or (staff_name == b and a in current_names):
            other = b if staff_name == a else a
            return False, f"Cannot be on the same shift as {other}"

    # 5. Shift restrictions
    if staff_name in STAFF_SHIFT_RESTRICTIONS:
        allowed = STAFF_SHIFT_RESTRICTIONS[staff_name]
        if shift not in allowed:
            return False, f"{staff_name} is restricted to shifts: {', '.join(allowed)}"

    # 6. BALLS constraint (No-Matrix pairing limit)
    if balls_full and no_matrix == 1 and current_no_matrix_count >= 1:
        return False, "BALLS=FULL — cannot pair two No-Matrix staff on this shift"

    # 7. Every shift must have at least one No-Matrix staff (unless disabled for grid scheduler)
    if enforce_no_matrix_rule and len(current_staff) == 1 and current_no_matrix_count == 0 and no_matrix == 0:
        return False, "Shift requires at least one No-Matrix staff member"

    return True, "Eligible"
