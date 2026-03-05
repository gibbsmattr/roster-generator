"""
Core roster-generation algorithm.

The RosterGenerator follows a three-stage process:
  1. PRE-ASSIGNMENT  – honour any manually locked-in assignments.
  2. TRUMP passes    – if only one staff member can fill a role on a shift,
                       assign them immediately (repeat until stable).
  3. VALHALLA pass   – assign remaining staff in seniority order, honouring
                       shift preferences where recorded.
"""

from typing import Dict, List, Tuple
import pandas as pd

from modules.config import DAY_SHIFTS, NIGHT_SHIFTS
from modules.shift_utils import can_staff_work_shift
from modules.logging_manager import get_logger


class RosterGenerator:
    """Generate a shift roster for one shift period (day or night)."""

    def __init__(
        self,
        staff_data: pd.DataFrame,
        prior_shifts: Dict[str, str],
        pre_assigned: Dict[str, str],
        metrics: Dict,
        dual_role_assignments: Dict[str, str],
        is_day_shift: bool = True,
        enforce_no_matrix_rule: bool = True,
    ):
        self.staff_data           = staff_data
        self.prior_shifts         = prior_shifts
        self.pre_assigned         = pre_assigned
        self.metrics              = metrics
        self.dual_role_assignments = dual_role_assignments
        self.is_day_shift         = is_day_shift
        self.enforce_no_matrix_rule = enforce_no_matrix_rule
        self.logger               = get_logger()

        self.shifts              = DAY_SHIFTS if is_day_shift else NIGHT_SHIFTS
        self.shift_assignments   = {shift: [] for shift in self.shifts}
        self.unassigned_staff:   List[str] = []
        self.unassigned_reasons: Dict[str, str] = {}

        # Ensure final_actual is always present.
        if "final_actual" not in metrics:
            metrics["final_actual"] = metrics.get("actual", 0)

        # Build the ordered list of shifts to staff (limited to final_actual).
        final_actual  = int(metrics["final_actual"])
        self.working_list: List[str] = [
            shift
            for shift, info in sorted(self.shifts.items(), key=lambda x: x[1]["rank"])
            if "rank" in info and int(info["rank"]) <= final_actual
        ]

        # BALLS = how many shifts can legally have two No-Matrix staff.
        nm  = metrics.get("no_matrix_count", 0)
        fa  = metrics.get("final_actual", 0)
        self.balls = max(0, int(nm) - int(fa)) if isinstance(nm, (int, float)) else 0
        self.no_matrix_shift_count = 0  # running count of shifts with 2 NM staff

    # ------------------------------------------------------------------
    # Stage 1 – Pre-assignments
    # ------------------------------------------------------------------

    def handle_pre_assignments(self):
        """Place staff that have been manually locked to specific shifts."""
        for name, shift in self.pre_assigned.items():
            if shift not in self.shifts:
                continue
            if name not in self.staff_data["STAFF NAME"].values:
                continue

            info = self.staff_data[self.staff_data["STAFF NAME"] == name].iloc[0]
            role = info["ROLE"]
            if role == "dual" and name in self.dual_role_assignments:
                role = self.dual_role_assignments[name]

            no_matrix = int(info.get("No Matrix", 0)) if pd.notna(info.get("No Matrix")) else 0
            self.shift_assignments[shift].append((name, role, no_matrix))
            self.logger.log_pre_assignment(name, shift, role, no_matrix)

            if no_matrix == 1:
                nm_on_shift = sum(1 for s in self.shift_assignments[shift] if s[2] == 1)
                if nm_on_shift > 1:
                    self.no_matrix_shift_count += 1

    # ------------------------------------------------------------------
    # Stage 2 – TRUMP (critical staffing)
    # ------------------------------------------------------------------

    def _analyze_options(self, working_staff: pd.DataFrame) -> Dict:
        """
        For each unfilled role on each working shift, list all eligible staff.

        Returns a nested dict: { shift: { role: [(name, no_matrix), ...] } }
        """
        options: Dict = {}
        balls_full = self.no_matrix_shift_count >= self.balls

        for shift in self.working_list:
            options[shift] = {"nurse": [], "medic": []}
            current = self.shift_assignments[shift]
            current_roles = [s[1] for s in current]

            if "nurse" in current_roles and "medic" in current_roles:
                continue  # Fully staffed.

            roles_needed = (
                ["medic"]  if "nurse" in current_roles else
                ["nurse"]  if "medic" in current_roles else
                ["nurse", "medic"]
            )
            current_nm = sum(1 for s in current if s[2] == 1)

            for role in roles_needed:
                # Direct-role staff
                candidates = list(working_staff[working_staff["ROLE"] == role].iterrows())
                # Dual staff assigned to this role
                dual_candidates = [
                    row for _, row in working_staff[working_staff["ROLE"] == "dual"].iterrows()
                    if self.dual_role_assignments.get(row["STAFF NAME"]) == role
                ]

                for staff_row in [r for _, r in candidates] + dual_candidates:
                    name      = staff_row["STAFF NAME"]
                    no_matrix = int(staff_row.get("No Matrix", 0)) if pd.notna(staff_row.get("No Matrix")) else 0
                    reduced   = bool(staff_row.get("Reduced Rest OK", False))

                    ok, _ = can_staff_work_shift(
                        name, role, shift, current,
                        self.prior_shifts, reduced, no_matrix,
                        balls_full, current_nm, self.enforce_no_matrix_rule,
                    )
                    if ok:
                        options[shift][role].append((name, no_matrix))

        return options

    def _critical_pass(self, options: Dict, working_staff: pd.DataFrame) -> Tuple[bool, pd.DataFrame]:
        """
        Assign any role that has exactly one eligible candidate (TRUMP).
        Returns (changed, updated_working_staff).
        """
        for shift in self.working_list:
            current_roles = [s[1] for s in self.shift_assignments[shift]]
            for role in ["nurse", "medic"]:
                if role in current_roles:
                    continue
                candidates = options[shift][role]
                if len(candidates) == 1:
                    name, no_matrix = candidates[0]
                    self.shift_assignments[shift].append((name, role, no_matrix))
                    self.logger.log_critical_assignment(name, shift, role, no_matrix, 1)
                    self._update_balls(shift, no_matrix)
                    updated = working_staff[working_staff["STAFF NAME"] != name]
                    return True, updated

        return False, working_staff

    def _update_balls(self, shift: str, no_matrix: int):
        """Recalculate the BALLS counter after a No-Matrix placement."""
        if no_matrix == 1:
            nm_count = sum(1 for s in self.shift_assignments[shift] if s[2] == 1)
            if nm_count > 1:
                self.no_matrix_shift_count += 1
                nm  = self.metrics.get("no_matrix_count", 0)
                fa  = self.metrics.get("final_actual", 0)
                self.balls = max(0, int(nm) - int(fa))

    # ------------------------------------------------------------------
    # Stage 3 – VALHALLA (seniority + preference)
    # ------------------------------------------------------------------

    def assign_staff_by_seniority(self, staff_df: pd.DataFrame):
        """
        Work through the staff list (most-senior first) and place each member
        on their highest-preference eligible shift.  Falls back to any eligible
        shift if no preference data is available.
        """
        current = staff_df.copy()

        while not current.empty:
            row        = current.iloc[0]
            name       = row["STAFF NAME"]
            role       = row["ROLE"]
            no_matrix  = int(row.get("No Matrix", 0)) if pd.notna(row.get("No Matrix")) else 0
            reduced    = bool(row.get("Reduced Rest OK", False))
            balls_full = self.no_matrix_shift_count >= self.balls

            if role == "dual" and name in self.dual_role_assignments:
                role = self.dual_role_assignments[name]

            # Skip if pre-assigned.
            if name in self.pre_assigned and self.pre_assigned[name] in self.shifts:
                current = current.iloc[1:]
                continue

            # Find all eligible shifts.
            eligible = []
            for shift in self.working_list:
                existing   = self.shift_assignments[shift]
                current_nm = sum(1 for s in existing if s[2] == 1)
                ok, _      = can_staff_work_shift(
                    name, role, shift, existing,
                    self.prior_shifts, reduced, no_matrix,
                    balls_full, current_nm, self.enforce_no_matrix_rule,
                )
                if ok:
                    eligible.append(shift)

            # Gather preference values for eligible shifts.
            prefs = []
            orig_row = self.staff_data[self.staff_data["STAFF NAME"] == name]
            if not orig_row.empty:
                orig = orig_row.iloc[0]
                for shift in eligible:
                    shift_rank = self.shifts[shift].get("rank", 999)
                    if shift in self.staff_data.columns:
                        val = orig.get(shift, 0)
                        pref_val = float(val) if pd.notna(val) and float(val) > 0 else 999
                    else:
                        pref_val = 999
                    # Store (shift, rank, preference) tuple
                    # We'll sort by rank first, then preference
                    prefs.append((shift, shift_rank, pref_val))

            # Sort by shift rank FIRST (lower = higher priority), 
            # then by preference value (lower = more preferred)
            # This ensures higher-priority shifts are filled before lower-priority ones
            prefs.sort(key=lambda x: (x[1], x[2]))

            assigned = False
            if prefs:
                best_shift, shift_rank, pref_val = prefs[0]
                self.shift_assignments[best_shift].append((name, role, no_matrix))
                self.logger.log_preference_assignment(name, best_shift, role, no_matrix, pref_val)
                self._update_balls(best_shift, no_matrix)
                assigned = True
            elif eligible:
                # Prioritise any shift that already has one slot filled (critical).
                critical = [
                    s for s in eligible
                    if len(self.shift_assignments[s]) == 1
                    and role not in [x[1] for x in self.shift_assignments[s]]
                ]
                best_shift = (critical or eligible)[0]
                self.shift_assignments[best_shift].append((name, role, no_matrix))
                self.logger.log_assignment(name, best_shift, role, no_matrix, "No preference — first available")
                self._update_balls(best_shift, no_matrix)
                assigned = True

            if not assigned:
                self.unassigned_staff.append(name)
                self.unassigned_reasons[name] = "No eligible shift available"
                self.logger.log_unassigned(name, "No eligible shift available")

            current = current.iloc[1:]

            # After each assignment, run TRUMP passes on remaining staff.
            if assigned and not current.empty:
                changed = True
                while changed and not current.empty:
                    opts    = self._analyze_options(current)
                    changed, current = self._critical_pass(opts, current)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_roster(self) -> Dict[str, List]:
        """Run all three stages and return the completed shift assignments."""
        self.logger.log_phase(
            f"{'Day' if self.is_day_shift else 'Night'} Roster Generation",
            f"Processing {len(self.staff_data)} staff across "
            f"{len(self.working_list)} shifts",
        )

        # Stage 1.
        self.handle_pre_assignments()

        # Build working DataFrame (exclude pre-assigned).
        pre_names = {name for shift, staff in self.shift_assignments.items() for name, _, _ in staff}
        the_list  = self.staff_data[~self.staff_data["STAFF NAME"].isin(pre_names)].copy()

        # Stage 2 – initial TRUMP passes.
        if not the_list.empty:
            changed = True
            while changed and not the_list.empty:
                opts    = self._analyze_options(the_list)
                changed, the_list = self._critical_pass(opts, the_list)

        # Stage 3 – VALHALLA.
        if not the_list.empty:
            if "Seniority" in the_list.columns:
                the_list = the_list.sort_values("Seniority", ascending=True)
            self.assign_staff_by_seniority(the_list)

        # Log any staff that ended up unaccounted for.
        all_assigned = {s[0] for staffed in self.shift_assignments.values() for s in staffed}
        for name in self.staff_data["STAFF NAME"]:
            if name not in all_assigned and name not in self.unassigned_staff:
                row = self.staff_data[self.staff_data["STAFF NAME"] == name]
                role = row.iloc[0]["ROLE"] if not row.empty else "unknown"
                self.logger.log_unassigned(name, f"No {('day' if self.is_day_shift else 'night')} shift for {role}")

        self.logger.log_phase("Roster Complete")
        return self.shift_assignments

    def get_unassigned_staff(self) -> List[Tuple[str, str]]:
        """Return list of (name, reason) for staff who could not be placed."""
        seen: set = set()
        result = []
        for name in self.unassigned_staff:
            if name not in seen:
                seen.add(name)
                result.append((name, self.unassigned_reasons.get(name, "Unknown reason")))
        return result

    def create_staff_view(self, staff_list: List[str]) -> pd.DataFrame:
        """
        Return a DataFrame mapping each staff member to their assigned shift code.

        Dual staff functioning as medics have a trailing 'p' appended to their
        shift code (e.g. 'MGp') so dispatchers can identify them.
        """
        orig_roles = {
            row["STAFF NAME"]: row["ROLE"]
            for _, row in self.staff_data.iterrows()
        }
        default = "D" if self.is_day_shift else "N"
        rows = []

        for name in staff_list:
            assignment = default
            actual_role = None
            for shift_name, staff_on_shift in self.shift_assignments.items():
                for s_name, s_role, _ in staff_on_shift:
                    if s_name == name:
                        assignment  = shift_name
                        actual_role = s_role
                        break
                if assignment != default:
                    break

            # Append 'p' for dual staff working as medics.
            if (
                assignment != default
                and actual_role == "medic"
                and orig_roles.get(name) == "dual"
            ):
                assignment += "p"

            rows.append({"STAFF NAME": name, "Assignment": assignment})

        return pd.DataFrame(rows)
