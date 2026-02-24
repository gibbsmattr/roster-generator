"""
Assignment logger for the Roster Generator.

Stores structured log entries in Streamlit session state so they survive
reruns, then renders them as organised tables and filterable log entries
in the UI.
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Any


class AssignmentLogger:
    """Accumulate and display structured log entries."""

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self):
        if "assignment_logs" not in st.session_state:
            st.session_state.assignment_logs = []

    def clear_logs(self):
        st.session_state.assignment_logs = []

    # ------------------------------------------------------------------
    # Low-level logging
    # ------------------------------------------------------------------

    def log(self, message: str, log_type: str = "info", details: Dict = None):
        """Append a structured log entry."""
        st.session_state.assignment_logs.append(
            {
                "message": message,
                "type": log_type,
                "details": details or {},
                "timestamp": len(st.session_state.assignment_logs),
            }
        )

    # ------------------------------------------------------------------
    # Typed helpers
    # ------------------------------------------------------------------

    def log_phase(self, phase_name: str, description: str = ""):
        """Mark the start of a named processing phase."""
        self.log(
            message=f"PHASE: {phase_name}",
            log_type="phase",
            details={"phase": phase_name, "description": description, "process_type": "phase"},
        )

    def log_decision(self, decision: str, context: Dict = None):
        self.log(
            message=f"DECISION: {decision}",
            log_type="decision",
            details=context or {},
        )

    def log_assignment(self, staff_name: str, shift: str, role: str, no_matrix: int, reason: str = ""):
        self.log(
            message=f"Assigned {staff_name} → {shift} as {role}",
            log_type="success",
            details={
                "staff_name": staff_name, "shift": shift, "role": role,
                "no_matrix": no_matrix, "reason": reason, "process_type": "standard",
            },
        )

    def log_critical_assignment(self, staff_name: str, shift: str, role: str, no_matrix: int, options_count: int):
        """Log a TRUMP (only-option) assignment."""
        self.log(
            message=f"CRITICAL: {staff_name} → {shift} as {role} (only option available)",
            log_type="warning",
            details={
                "staff_name": staff_name, "shift": shift, "role": role,
                "no_matrix": no_matrix, "options_count": options_count,
                "process_type": "TRUMP",
                "reason": f"Only option for {shift} {role}",
            },
        )

    def log_preference_assignment(self, staff_name: str, shift: str, role: str, no_matrix: int, pref_value: float):
        """Log a VALHALLA (preference-driven) assignment."""
        self.log(
            message=f"PREFERENCE: {staff_name} → {shift} as {role} (pref={pref_value})",
            log_type="info",
            details={
                "staff_name": staff_name, "shift": shift, "role": role,
                "no_matrix": no_matrix, "preference": pref_value,
                "process_type": "VALHALLA",
                "reason": f"Preference value {pref_value} for {shift}",
            },
        )

    def log_pre_assignment(self, staff_name: str, shift: str, role: str, no_matrix: int):
        self.log(
            message=f"PRE-ASSIGNED: {staff_name} → {shift} as {role}",
            log_type="info",
            details={
                "staff_name": staff_name, "shift": shift, "role": role,
                "no_matrix": no_matrix, "process_type": "PRE-ASSIGNMENT",
                "reason": "Manually pre-assigned",
            },
        )

    def log_unassigned(self, staff_name: str, reason: str):
        self.log(
            message=f"UNASSIGNED: {staff_name} — {reason}",
            log_type="error",
            details={"staff_name": staff_name, "reason": reason, "process_type": "unassigned"},
        )

    # ------------------------------------------------------------------
    # Summary DataFrames
    # ------------------------------------------------------------------

    def _assignment_logs(self) -> List[Dict]:
        """Return only logs that represent an actual staff placement."""
        return [
            e for e in st.session_state.assignment_logs
            if e["details"].get("process_type") in
               {"standard", "TRUMP", "VALHALLA", "PRE-ASSIGNMENT"}
            and "staff_name" in e["details"]
            and "shift" in e["details"]
        ]

    def get_staff_assignment_summary(self) -> pd.DataFrame:
        """One row per staff member showing their final assignment."""
        rows = []
        seen_names: set = set()

        for entry in self._assignment_logs():
            d = entry["details"]
            name = d["staff_name"]
            if name not in seen_names:
                seen_names.add(name)
                rows.append({
                    "Staff Name":        name,
                    "Shift":             d["shift"],
                    "Role":              d.get("role", ""),
                    "No Matrix":         "Yes" if d.get("no_matrix") == 1 else "No",
                    "Assignment Method": d["process_type"],
                    "Reason":            d.get("reason", ""),
                })

        # Append any staff logged as unassigned who aren't already in the table.
        for entry in st.session_state.assignment_logs:
            d = entry["details"]
            if d.get("process_type") == "unassigned" and d.get("staff_name") not in seen_names:
                seen_names.add(d["staff_name"])
                rows.append({
                    "Staff Name":        d["staff_name"],
                    "Shift":             "UNASSIGNED",
                    "Role":              "",
                    "No Matrix":         "",
                    "Assignment Method": "UNASSIGNED",
                    "Reason":            d.get("reason", ""),
                })

        columns = ["Staff Name", "Shift", "Role", "No Matrix", "Assignment Method", "Reason"]
        return pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame(columns=columns)

    def get_shift_assignment_timeline(self) -> pd.DataFrame:
        """Chronological list of all assignment events."""
        rows = [
            {
                "Step":   entry["timestamp"],
                "Shift":  entry["details"]["shift"],
                "Staff":  entry["details"]["staff_name"],
                "Role":   entry["details"].get("role", ""),
                "Method": entry["details"]["process_type"],
                "Reason": entry["details"].get("reason", ""),
            }
            for entry in self._assignment_logs()
        ]
        columns = ["Step", "Shift", "Staff", "Role", "Method", "Reason"]
        if rows:
            return pd.DataFrame(rows, columns=columns).sort_values("Step")
        return pd.DataFrame(columns=columns)

    # ------------------------------------------------------------------
    # UI rendering
    # ------------------------------------------------------------------

    def display_logs_ui(self, title: str = "Assignment Process Analysis"):
        """Render log data inside a collapsible section with multiple sub-tabs."""
        with st.expander(title, expanded=False):
            if not st.session_state.assignment_logs:
                st.info("No logs yet — generate a roster first.")
                return

            tabs = st.tabs(["Staff Summary", "Timeline", "Unassigned", "Detailed Logs"])
            staff_summary = self.get_staff_assignment_summary()

            # Tab 1 – Staff summary
            with tabs[0]:
                st.subheader("Staff Assignment Summary")
                if not staff_summary.empty:
                    st.dataframe(staff_summary, use_container_width=True, hide_index=True)
                else:
                    st.info("No assignments recorded.")

            # Tab 2 – Timeline
            with tabs[1]:
                st.subheader("Shift Assignment Timeline")
                timeline = self.get_shift_assignment_timeline()
                if not timeline.empty:
                    st.dataframe(timeline, use_container_width=True, hide_index=True)
                else:
                    st.info("No timeline data.")

            # Tab 3 – Unassigned staff
            with tabs[2]:
                st.subheader("Unassigned Staff")
                unassigned = staff_summary[staff_summary["Shift"] == "UNASSIGNED"]
                if not unassigned.empty:
                    st.dataframe(
                        unassigned[["Staff Name", "Reason"]],
                        use_container_width=True, hide_index=True,
                    )
                else:
                    st.success("All staff have been assigned.")

            # Tab 4 – Detailed filterable log
            with tabs[3]:
                st.subheader("Detailed Logs")
                log_types = ["All"] + sorted(
                    {e["type"] for e in st.session_state.assignment_logs}
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    selected_type = st.selectbox("Filter by type:", log_types, key="log_type_filter")
                with col_b:
                    search_term = st.text_input("Search:", "", key="log_search")

                filtered = st.session_state.assignment_logs
                if selected_type != "All":
                    filtered = [e for e in filtered if e["type"] == selected_type]
                if search_term:
                    filtered = [e for e in filtered if search_term.lower() in e["message"].lower()]

                for entry in filtered:
                    t = entry["type"]
                    msg = entry["message"]
                    if t == "phase":
                        st.markdown(f"#### {msg}")
                        if entry["details"].get("description"):
                            st.caption(entry["details"]["description"])
                        st.divider()
                    elif t == "decision":
                        st.markdown(f"**{msg}**")
                    elif t == "error":
                        st.error(msg)
                    elif t == "warning":
                        st.warning(msg)
                    elif t == "success":
                        st.success(msg)
                    else:
                        st.info(msg)

            # Download options
            st.divider()
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    "⬇ Download Staff Summary (CSV)",
                    data=staff_summary.to_csv(index=False).encode("utf-8"),
                    file_name="staff_assignments.csv",
                    mime="text/csv",
                )
            with dl_col2:
                logs_df = pd.DataFrame([
                    {"Step": e["timestamp"], "Type": e["type"], "Message": e["message"]}
                    for e in st.session_state.assignment_logs
                ])
                st.download_button(
                    "⬇ Download Full Logs (CSV)",
                    data=logs_df.to_csv(index=False).encode("utf-8"),
                    file_name="assignment_logs.csv",
                    mime="text/csv",
                )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

def get_logger() -> AssignmentLogger:
    """Return the session-scoped singleton logger."""
    if "logger" not in st.session_state:
        st.session_state.logger = AssignmentLogger()
    return st.session_state.logger
