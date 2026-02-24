"""
Data loading and processing functions for the Roster Generator.

Handles reading the staff Excel file, parsing text input from the UI,
and calculating staffing metrics.
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

from modules.config import BASE_TO_SHIFTS, DAY_SHIFTS, NIGHT_SHIFTS


# ---------------------------------------------------------------------------
# Excel loading
# ---------------------------------------------------------------------------

def load_staff_data_from_path(file_path: str) -> pd.DataFrame:
    """Load staff data from an Excel file path and return a processed DataFrame."""
    df = pd.read_excel(file_path)
    return _process_staff_data(df)


def load_staff_data(file) -> pd.DataFrame:
    """Load staff data from a Streamlit UploadedFile object."""
    df = pd.read_excel(file)
    return _process_staff_data(df)


def _process_staff_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalise the raw staff DataFrame.

    Required columns: STAFF NAME, ROLE, Seniority, No Matrix
    Optional columns: Reduced Rest OK, base preference columns (from BASE_TO_SHIFTS)
    """
    required = ["STAFF NAME", "ROLE", "Seniority", "No Matrix"]
    for col in required:
        if col not in df.columns:
            raise ValueError(
                f"Required column '{col}' not found in the staff data file.\n"
                f"Columns present: {list(df.columns)}"
            )

    # -- No Matrix -------------------------------------------------------
    df["No Matrix"] = df["No Matrix"].fillna(0).astype(int)

    # -- Reduced Rest OK -------------------------------------------------
    reduced_col = next(
        (c for c in ["Reduced Rest OK", "REDUCED_REST_OK"] if c in df.columns),
        None,
    )
    if reduced_col:
        df["Reduced Rest OK"] = (
            pd.to_numeric(df[reduced_col], errors="coerce").fillna(0) == 1
        )
    else:
        df["Reduced Rest OK"] = False

    # -- Seniority -------------------------------------------------------
    df["Seniority"] = df["Seniority"].fillna(0).astype(float)

    # -- Shift preferences -----------------------------------------------
    # Prefer the base-column format (BASE_TO_SHIFTS keys) over individual shift columns.
    base_cols_found = [c for c in BASE_TO_SHIFTS if c in df.columns]

    if base_cols_found:
        # New format: expand each base column into its child shift columns.
        for base in base_cols_found:
            base_prefs = pd.to_numeric(df[base], errors="coerce").fillna(0)
            df[base] = base_prefs
            for shift in BASE_TO_SHIFTS[base]:
                df[shift] = base_prefs
    else:
        # Legacy format: individual shift columns already present.
        all_shifts = list(DAY_SHIFTS) + list(NIGHT_SHIFTS)
        for shift in all_shifts:
            if shift in df.columns:
                df[shift] = pd.to_numeric(df[shift], errors="coerce").fillna(0)

    return df


# ---------------------------------------------------------------------------
# Shift code utilities
# ---------------------------------------------------------------------------

def normalize_shift_code(shift_code: str) -> str:
    """Remove trailing 'p' suffix from a shift code (dual-as-medic marker)."""
    if shift_code and shift_code.endswith("p"):
        return shift_code[:-1]
    return shift_code


# ---------------------------------------------------------------------------
# Text-input parsing
# ---------------------------------------------------------------------------

# Matches standard shift codes AND special codes, with optional trailing 'p'.
_SHIFT_RE = re.compile(
    r"\b([DN][0-9]+[A-Z]+p?|FWp?|MGp?|GRp?|LGp?|PGp?|NGp?|NPp?)\b"
)


def parse_staff_input(input_text: str) -> Tuple[List[str], Dict[str, str]]:
    """
    Parse the free-text staff input from the UI.

    Each line should be:  ``<Name>  [prior_shift]``
    (tab-separated, or separated by 4+ spaces)

    Returns:
        staff_list  – ordered list of staff names
        prior_shifts – mapping of name → prior shift code (may include 'p' suffix)
    """
    staff_list: List[str] = []
    prior_shifts: Dict[str, str] = {}

    if not input_text or not input_text.strip():
        return staff_list, prior_shifts

    for raw_line in input_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Try to find a shift code anywhere in the line.
        match = _SHIFT_RE.search(line)
        if match:
            shift_code = match.group(0)
            name = line[: match.start()].strip().rstrip("\t ")
        else:
            # No shift code found — split on tab or 4+ spaces.
            if "\t" in line:
                parts = [p.strip() for p in line.split("\t") if p.strip()]
            else:
                parts = [p.strip() for p in re.split(r"\s{4,}", line) if p.strip()]

            name = parts[0] if parts else ""
            shift_code = None
            if len(parts) > 1 and _SHIFT_RE.match(parts[1]):
                shift_code = parts[1]

        if not name:
            continue

        staff_list.append(name)
        if shift_code:
            prior_shifts[name] = shift_code

    return staff_list, prior_shifts


def parse_calculator_input(input_text: str) -> Tuple[List[str], List[str]]:
    """
    Parse the staffing-calculator input (name + 'D'/'N' indicator per line).

    Returns:
        day_staff_list, night_staff_list
    """
    day_list: List[str] = []
    night_list: List[str] = []

    if not input_text or not input_text.strip():
        return day_list, night_list

    for raw_line in input_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if "\t" in line:
            parts = [p.strip() for p in line.split("\t") if p.strip()]
        else:
            parts = line.split()

        if len(parts) < 2:
            continue

        indicator = parts[-1].upper()
        if indicator not in ("D", "N"):
            continue

        name = " ".join(parts[:-1])
        if indicator == "D":
            day_list.append(name)
        else:
            night_list.append(name)

    return day_list, night_list


# ---------------------------------------------------------------------------
# Staffing metrics
# ---------------------------------------------------------------------------

def calculate_staffing_metrics(staff_data: pd.DataFrame) -> Dict:
    """
    Compute core staffing metrics from a (pre-filtered) staff DataFrame.

    Key outputs:
    - nurse_count, medic_count, dual_count, total_staff
    - no_matrix_count
    - zenith  – maximum shifts based on total headcount (staff // 2)
    - actual  – min(zenith, no_matrix_count) — shifts that can actually be staffed
    - role_delta, role_needed, role_excess
    """
    m: Dict = {}
    m["nurse_count"]    = int(np.sum(staff_data["ROLE"] == "nurse"))
    m["medic_count"]    = int(np.sum(staff_data["ROLE"] == "medic"))
    m["dual_count"]     = int(np.sum(staff_data["ROLE"] == "dual"))
    m["total_staff"]    = len(staff_data)
    m["no_matrix_count"] = int(
        np.sum(staff_data.get("No Matrix", pd.Series([0] * len(staff_data))) == 1)
    )
    m["zenith"] = m["total_staff"] // 2
    m["actual"] = min(m["zenith"], m["no_matrix_count"])
    m["role_delta"] = abs(m["nurse_count"] - m["medic_count"])

    if m["nurse_count"] < m["medic_count"]:
        m["role_needed"] = "nurse"
        m["role_excess"] = "medic"
    else:
        m["role_needed"] = "medic"
        m["role_excess"] = "nurse"

    return m


def balance_dual_staff(staff_data: pd.DataFrame, metrics: Dict) -> Dict[str, str]:
    """
    Assign dual-role staff to 'nurse' or 'medic' to minimise role imbalance.

    Most-senior dual staff (lowest Seniority number) are used first.
    Returns a dict mapping staff name → assigned role.
    """
    assignments: Dict[str, str] = {}
    dual = staff_data[staff_data["ROLE"] == "dual"].copy()

    if "Seniority" in dual.columns:
        dual = dual.sort_values("Seniority", ascending=True)

    delta       = metrics["role_delta"]
    role_needed = metrics["role_needed"]

    for i, (_, row) in enumerate(dual.iterrows()):
        name = row["STAFF NAME"]
        if i < delta:
            # Fill the shortage first.
            assignments[name] = role_needed
        else:
            # Distribute remaining dual staff evenly.
            assignments[name] = "nurse" if (i - delta) % 2 == 0 else "medic"

    return assignments


def recalculate_balanced_metrics(metrics: Dict, dual_assignments: Dict[str, str]) -> Dict:
    """
    Recalculate nurse/medic counts and final_actual after dual-staff balancing.
    """
    updated = metrics.copy()
    updated["balanced_nurse_count"] = metrics["nurse_count"]
    updated["balanced_medic_count"] = metrics["medic_count"]

    for role in dual_assignments.values():
        if role == "nurse":
            updated["balanced_nurse_count"] += 1
        else:
            updated["balanced_medic_count"] += 1

    # final_actual is constrained by the limiting role after balancing.
    base_actual = metrics.get("actual", 0)
    updated["final_actual"] = min(
        base_actual,
        updated["balanced_nurse_count"],
        updated["balanced_medic_count"],
    )

    return updated


def prepare_staffing_list(
    staff_data: pd.DataFrame,
    dual_assignments: Dict[str, str],
    pre_assigned: Dict[str, str],
    shift_dict: Dict,
) -> pd.DataFrame:
    """
    Build the working staff list for the roster generator.

    Excludes pre-assigned staff and replaces dual-staff 'ROLE' with their
    balanced assignment.  Result is sorted by Seniority (ascending).
    """
    rows = []
    for _, staff in staff_data.iterrows():
        name = staff["STAFF NAME"]
        if name in pre_assigned and pre_assigned[name] in shift_dict:
            continue  # Already placed; skip.
        entry = staff.copy()
        if staff["ROLE"] == "dual" and name in dual_assignments:
            entry["ROLE"] = dual_assignments[name]
        rows.append(entry)

    result = pd.DataFrame(rows)
    if not result.empty and "Seniority" in result.columns:
        result = result.sort_values("Seniority", ascending=True)
    return result
