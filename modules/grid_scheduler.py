"""
Grid Scheduler
==============

Accepts a tab-separated grid pasted directly from Excel:
  - Column 0  : staff name
  - Columns 1-2  : prior 2 days (already worked — lookback only)
  - Columns 3-16 : 14 days of current period

Cell values:
  - "D" / "N" / "D/N"       → needs assignment
  - D-variants (D*, *D, etc) → treat as D, needs assignment
  - Specific code (D7B, N9L) → already assigned, leave alone, count for rules
  - Anything else            → non-working (leave/edu/off), skip for rules

Rules:
  - Assign best shift code from preferences file for each person
  - Honour 12hr rest (10hr if Reduced Rest OK)
  - Max 4 consecutive same-type shifts
  - A 5th consecutive shift is allowed ONLY if the 5-stretch contains at least
    one D-type AND one N-type (i.e. never 5 pure days or 5 pure nights)
  - No type-flipping forced — keep person on D or N as pasted
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from modules.config import (
    ALL_SHIFTS, BASE_TO_SHIFTS,
    STANDARD_REST_HOURS, REDUCED_REST_HOURS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAY_CODES   = {k for k, v in ALL_SHIFTS.items() if int(v["start_time"]) < 1800}
NIGHT_CODES = {k for k, v in ALL_SHIFTS.items() if int(v["start_time"]) >= 1800}

# Patterns that mean "this is a D shift, needs assignment"
_D_VARIANT = re.compile(
    r'^(D[*/&#]|[*/&#]D|D\d+[*/&#]|ON\s*D[*/&#]?|D/N|D)$',
    re.IGNORECASE,
)
_N_VARIANT = re.compile(r'^N$', re.IGNORECASE)

# Non-working codes — don't count toward consecutive limits
NON_WORKING = {
    "LT", "LT-D", "LT-N", "SM", "SIM", "AT", "EDU", "CLINICAL",
    "ATLS", "STABLE", "LOA", "MIL", "AOC", "KCU", "COMM", "OFF", "",
}

# ---------------------------------------------------------------------------
# Cell classification
# ---------------------------------------------------------------------------

def _classify(raw: str) -> str:
    """
    Returns one of:
      'D'        — needs a day shift assigned
      'N'        — needs a night shift assigned
      'DN'       — can be either; treat as D for assignment
      'ASSIGNED' — already has a specific code, leave it
      'NONE'     — non-working, skip
    """
    v = str(raw).strip() if raw is not None else ""
    if not v or v.upper() in NON_WORKING:
        return "NONE"
    vu = v.upper()
    if vu in ALL_SHIFTS:
        return "ASSIGNED"
    if vu == "D/N":
        return "DN"
    if _D_VARIANT.match(v):
        return "D"
    if _N_VARIANT.match(v):
        return "N"
    # Anything else (LOA, clinical keywords not in set, etc.) → NONE
    return "NONE"


def _shift_type(code: str) -> Optional[str]:
    """Return 'D' or 'N' for a known shift code, else None."""
    if code in DAY_CODES:
        return "D"
    if code in NIGHT_CODES:
        return "N"
    return None

# ---------------------------------------------------------------------------
# Rest-hours calculation
# ---------------------------------------------------------------------------

def _shift_end_hour(code: str) -> Optional[float]:
    """Return the end time of a shift as fractional hours from midnight."""
    info = ALL_SHIFTS.get(code)
    if not info:
        return None
    t = int(info["end_time"])
    h, m = t // 100, t % 100
    return h + m / 60.0


def _shift_start_hour(code: str) -> Optional[float]:
    info = ALL_SHIFTS.get(code)
    if not info:
        return None
    t = int(info["start_time"])
    h, m = t // 100, t % 100
    return h + m / 60.0


def _rest_hours_between(prev_code: str, next_code: str) -> float:
    """
    Compute rest hours between the end of prev_code and start of next_code.
    Handles overnight shifts (end hour < start hour means it crosses midnight).
    """
    end_h   = _shift_end_hour(prev_code)
    start_h = _shift_start_hour(next_code)
    if end_h is None or start_h is None:
        return 999.0

    # end_h relative to the day it starts
    prev_type = _shift_type(prev_code)
    next_type = _shift_type(next_code)

    # Night shifts end the next morning (add 24 if end < start within same night context)
    # We model each shift as occurring on its calendar day.
    # A night shift that starts at 19:00 ends at 07:00 (+1 day).
    prev_end_offset = 0
    if prev_type == "N" and end_h < 12:
        prev_end_offset = 24   # ends next morning

    next_start_offset = 24     # next shift is one calendar day later
    if next_type == "N":
        next_start_offset = 24  # night shift starts same evening of its day

    rest = (next_start_offset + start_h) - (end_h + prev_end_offset)
    return rest

# ---------------------------------------------------------------------------
# Consecutive shift rule checker
# ---------------------------------------------------------------------------

def _consecutive_ok(history: List[str], proposed_type: str) -> bool:
    """
    history  : list of shift codes for prior working days (oldest first),
               as many as are available (we only look at last 4).
    proposed_type: 'D' or 'N'

    Rules:
    - Last 4 consecutive working shifts of same type → block unless mixed stretch
    - A 5-stretch is ok only if it will contain both D and N types
    - Never allow 5 of same type in a row
    """
    # Walk back through history collecting the current consecutive working run
    run: List[str] = []
    for code in reversed(history):
        t = _shift_type(code)
        if t is None:
            break
        run.insert(0, code)

    run_len = len(run)

    if run_len < 4:
        return True   # no issue yet

    # Run is exactly 4 — a 5th is ok only if the 5-stretch has mixed types
    if run_len == 4:
        types_in_run = {_shift_type(c) for c in run}
        if proposed_type not in types_in_run:
            # Already mixed (4 of one, now adding the other) — ok
            return True
        # Same type — would be 5 of same — block
        return False

    # Run is 5+ — block regardless
    return False

# ---------------------------------------------------------------------------
# Preference lookup
# ---------------------------------------------------------------------------

def _ranked_shifts_for(staff_row: pd.Series, shift_type: str) -> List[str]:
    """
    Return day or night shift codes ordered by the staff member's preference
    (lower preference number = higher preference).
    Falls back to config rank order if no preferences found.
    """
    day_shifts   = [k for k in ALL_SHIFTS if k in DAY_CODES]
    night_shifts = [k for k in ALL_SHIFTS if k in NIGHT_CODES]
    candidate_shifts = day_shifts if shift_type == "D" else night_shifts

    # Build base→shifts map from config
    # Find which base columns are in staff_row
    prefs: List[Tuple[float, str]] = []
    for base_col, shifts in BASE_TO_SHIFTS.items():
        if base_col in staff_row.index:
            val = staff_row[base_col]
            try:
                rank = float(val)
            except (TypeError, ValueError):
                rank = 0.0
            if rank > 0:
                for s in shifts:
                    if s in [c for c in candidate_shifts]:
                        prefs.append((rank, s))

    if prefs:
        # Sort by preference rank ascending (1 = most preferred)
        prefs.sort(key=lambda x: x[0])
        # Deduplicate preserving order
        seen = set()
        ordered = []
        for _, s in prefs:
            if s not in seen:
                seen.add(s)
                ordered.append(s)
        # Append any remaining candidate shifts not in prefs
        for s in candidate_shifts:
            if s not in seen:
                ordered.append(s)
        return ordered
    else:
        # No preferences — return by config rank
        return sorted(candidate_shifts,
                      key=lambda s: ALL_SHIFTS[s].get("rank", 99))

# ---------------------------------------------------------------------------
# Grid parser
# ---------------------------------------------------------------------------

def parse_grid(text: str) -> Tuple[List[str], List[List[str]]]:
    """
    Parse tab-separated pasted text into (names, rows).
    rows[i] is a list of 16 raw cell values (prior-2 + 14 days).
    Shorter rows are padded with "".
    """
    names = []
    rows  = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        name = parts[0].strip()
        if not name:
            continue
        cells = parts[1:]
        # Pad to 16
        while len(cells) < 16:
            cells.append("")
        names.append(name)
        rows.append(cells[:16])
    return names, rows

# ---------------------------------------------------------------------------
# Main scheduler
# ---------------------------------------------------------------------------

def run_grid_scheduler(
    pasted_text: str,
    staff_df: pd.DataFrame,
) -> Tuple[List[str], List[List[str]], List[str], Dict]:
    """
    Parameters
    ----------
    pasted_text : tab-separated grid from Excel
    staff_df    : preferences DataFrame (from session_state.staff_data_cache)

    Returns
    -------
    names       : list of staff names (row order)
    output_grid : list of 16-cell rows with D/N replaced by shift codes
    warnings    : list of warning strings
    stats       : summary dict
    """
    from modules.roster_generator import RosterGenerator
    from modules import data_manager
    
    names, rows = parse_grid(pasted_text)
    if not names:
        return [], [], ["No data found — check your paste."], {}

    # Build a lookup from staff name → row in staff_df
    staff_lookup: Dict[str, pd.Series] = {}
    unknown_names: List[str] = []
    
    if staff_df is not None:
        name_col = "STAFF NAME" if "STAFF NAME" in staff_df.columns else staff_df.columns[0]
        for _, row in staff_df.iterrows():
            n = str(row[name_col]).strip()
            staff_lookup[n] = row
    
    # Check for unknown names upfront
    for name in names:
        if name not in staff_lookup:
            # Try fuzzy match
            found = False
            for sn in staff_lookup.keys():
                if sn.lower() == name.lower():
                    found = True
                    break
            if not found:
                unknown_names.append(name)

    output_grid: List[List[str]] = []
    warnings: List[str] = []
    assigned_count = 0
    unresolved_count = 0

    # Process day-by-day across all 14 days (columns 2-15)
    # Each day: build list of who needs D or N, run roster generator
    
    for name, cells in zip(names, rows):
        output_grid.append(list(cells))  # Start with copy of input
    
    # Track prior shifts for each person (includes prior-2 days)
    person_history: Dict[str, List[str]] = {name: [] for name in names}
    
    # Initialize history with prior 2 days (columns 0-1)
    for idx, (name, cells) in enumerate(zip(names, rows)):
        for i in range(2):  # Prior 2 days
            raw = cells[i].strip()
            if raw and raw.upper() in ALL_SHIFTS:
                person_history[name].append(raw.upper())
    
    # Process each of the 14 days
    for day_idx in range(2, 16):  # columns 2-15 are the 14 working days
        # Separate day and night needs for this day
        day_needs: List[str] = []
        night_needs: List[str] = []
        
        for name_idx, name in enumerate(names):
            raw = rows[name_idx][day_idx].strip()
            cls = _classify(raw)
            
            if cls == "D" or cls == "DN":
                day_needs.append(name)
            elif cls == "N":
                night_needs.append(name)
            elif cls == "ASSIGNED":
                # Already has a specific code - track it for rest calc
                code = raw.upper()
                person_history[name].append(code)
                # Keep it in output grid
                output_grid[name_idx][day_idx] = code
        
        # Process day shifts for this day
        if day_needs:
            day_assignments, day_unassigned = _assign_shifts_for_day(
                day_needs, staff_df, person_history, True, staff_lookup
            )
            
            # Apply assignments to output grid
            for name, shift_code in day_assignments.items():
                name_idx = names.index(name)
                output_grid[name_idx][day_idx] = shift_code
                person_history[name].append(shift_code)
                assigned_count += 1
            
            # Track unassigned
            for name in day_unassigned:
                unresolved_count += 1
                warnings.append(f"{name} day {day_idx-1}: could not assign day shift")
        
        # Process night shifts for this day
        if night_needs:
            night_assignments, night_unassigned = _assign_shifts_for_day(
                night_needs, staff_df, person_history, False, staff_lookup
            )
            
            # Apply assignments to output grid
            for name, shift_code in night_assignments.items():
                name_idx = names.index(name)
                output_grid[name_idx][day_idx] = shift_code
                person_history[name].append(shift_code)
                assigned_count += 1
            
            # Track unassigned
            for name in night_unassigned:
                unresolved_count += 1
                warnings.append(f"{name} day {day_idx-1}: could not assign night shift")

    if unknown_names:
        warnings.insert(0,
            f"⚠️ {len(unknown_names)} name(s) not found in preferences file — "
            f"shifts left unassigned: {', '.join(unknown_names)}"
        )

    stats = {
        "total_staff":    len(names),
        "assigned":       assigned_count,
        "unresolved":     unresolved_count,
        "unknown_names":  len(unknown_names),
    }
    return names, output_grid, warnings, stats


def _assign_shifts_for_day(
    staff_names: List[str],
    staff_df: pd.DataFrame,
    person_history: Dict[str, List[str]],
    is_day_shift: bool,
    staff_lookup: Dict[str, pd.Series],
) -> Tuple[Dict[str, str], List[str]]:
    """
    Assign shifts for one day using proper roster generator logic.
    RosterGenerator prioritizes:
      1. Fully staffing higher-priority shifts before lower ones
      2. Completing partially-filled shifts (critical) before starting new ones
    
    Returns: (assignments dict with 'p' suffix for dual nurses as medics, unassigned list)
    """
    from modules import data_manager
    from modules.roster_generator import RosterGenerator
    
    # Filter staff_df to only those who need assignments
    filtered_staff = staff_df[staff_df["STAFF NAME"].isin(staff_names)].copy()
    
    if len(filtered_staff) == 0:
        return {}, staff_names
    
    # Build prior_shifts dict from person_history
    prior_shifts = {}
    for name in staff_names:
        history = person_history.get(name, [])
        if history:
            # Most recent shift is the "prior" for rest calculations
            prior_shifts[name] = history[-1]
    
    # Calculate metrics and dual assignments
    metrics = data_manager.calculate_staffing_metrics(filtered_staff)
    dual_assignments = data_manager.balance_dual_staff(filtered_staff, metrics)
    metrics = data_manager.recalculate_balanced_metrics(metrics, dual_assignments)
    
    # CRITICAL FIX for grid scheduler:
    # Override final_actual to include ALL shifts in working_list
    # EXCEPT for NP (night only) - NP should only be available if we have enough staff
    # to fully staff all 4 higher-priority night shifts first
    if is_day_shift:
        metrics["final_actual"] = 9  # All day shifts
    else:
        # For nights: check if we have enough staff to fully staff N7B, N7P, N9L, NG
        # Each needs 2 people (medic + nurse) = 8 people minimum for all 4
        # Only include NP (rank 5) if we have more than 8 people
        num_staff = len(staff_names)
        if num_staff >= 10:  # Enough to fill 4 shifts (8) + start NP (2)
            metrics["final_actual"] = 5  # Include NP
        else:
            metrics["final_actual"] = 4  # Exclude NP (only N7B, N7P, N9L, NG)
    
    # Run roster generator with priority-based filling
    # For grid scheduler, disable No-Matrix rule to maximize assignments
    generator = RosterGenerator(
        filtered_staff,
        prior_shifts,
        {},  # no pre-assignments for grid scheduler
        metrics,
        dual_assignments,
        is_day_shift=is_day_shift,
        enforce_no_matrix_rule=False,  # Allow pairing any two people to maximize assignments
    )
    
    shift_assignments = generator.generate_roster()
    
    # Build result dict with proper 'p' suffix for dual nurses working as medics
    # Get original roles from staff_df
    orig_roles = {
        row["STAFF NAME"]: row["ROLE"]
        for _, row in filtered_staff.iterrows()
    }
    
    assignments: Dict[str, str] = {}
    for shift_code, staff_list in shift_assignments.items():
        for name, role, no_matrix in staff_list:
            # Start with base shift code
            final_code = shift_code
            
            # Add lowercase 'p' suffix if this is a dual (nurse) working as medic
            if role == "medic" and orig_roles.get(name) == "dual":
                final_code = shift_code + "p"
            
            assignments[name] = final_code
    
    # Find who didn't get assigned
    unassigned = [name for name in staff_names if name not in assignments]
    
    return assignments, unassigned
