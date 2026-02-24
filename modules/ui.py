"""
Streamlit UI components for the Roster Generator.

Layout priority:
  1. Staff assignment tables — shown immediately, full width, at the top of results
  2. Everything else (metrics, shift view, logs) — collapsed by default
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Tuple

from modules.config import DAY_SHIFTS, NIGHT_SHIFTS, ORG_NAME, PAGE_LAYOUT, PAGE_ICON


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

def setup_page():
    st.set_page_config(page_title=ORG_NAME, layout=PAGE_LAYOUT, page_icon=PAGE_ICON)
    st.title(f"{PAGE_ICON} {ORG_NAME}")


# ---------------------------------------------------------------------------
# Staff input
# ---------------------------------------------------------------------------

def staff_input_section() -> Tuple[str, str]:
    """Side-by-side day / night staff text areas."""
    st.subheader("Staff Lists")

    instructions = (
        "Paste one name per row. Add a prior-shift code after a tab if needed:\n\n"
        "```\nSmith J.    D7B\nBarksdale\nGarcia M.   N7P\n```"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Day Shift**")
        with st.expander("Input instructions", expanded=False):
            st.markdown(instructions)
        day_input = st.text_area(
            "Day shift staff",
            value=st.session_state.get("day_staff_input", ""),
            height=300,
            key="day_staff_input",
            placeholder="Paste day shift names here...",
        )

    with col2:
        st.markdown("**Night Shift**")
        with st.expander("Input instructions", expanded=False):
            st.markdown(instructions)
        night_input = st.text_area(
            "Night shift staff",
            value=st.session_state.get("night_staff_input", ""),
            height=300,
            key="night_staff_input",
            placeholder="Paste night shift names here...",
        )

    return day_input, night_input


# ---------------------------------------------------------------------------
# Pre-assignment  (collapsed by default)
# ---------------------------------------------------------------------------

def pre_assignment_section(day_staff: List[str], night_staff: List[str]) -> Dict[str, str]:
    """
    Dropdowns to lock a staff member to a specific shift.
    Collapsed by default — users only open when needed.
    """
    if "staff_assignments" not in st.session_state:
        st.session_state.staff_assignments = {}

    active = len(st.session_state.staff_assignments)
    label  = "🔒 Pre-Assign Staff (optional)" + (f" — {active} active" if active else "")

    day_pre   = {}
    night_pre = {}

    with st.expander(label, expanded=False):
        col1, col2 = st.columns(2)

        def _render(staff_list, shift_options, prefix):
            pre = {}
            if not staff_list:
                st.info("Paste staff names above first.")
                return pre
            for i, name in enumerate(staff_list):
                saved   = st.session_state.staff_assignments.get(name)
                keys    = list(shift_options.keys())
                default = (keys.index(saved) + 1) if saved in keys else 0
                chosen  = st.selectbox(
                    name, ["None"] + keys, index=default, key=f"{prefix}_{i}"
                )
                if chosen != "None":
                    pre[name] = chosen
                    st.session_state.staff_assignments[name] = chosen
                elif name in st.session_state.staff_assignments:
                    del st.session_state.staff_assignments[name]
            return pre

        with col1:
            st.markdown("**Day Shift**")
            day_pre = _render(day_staff, DAY_SHIFTS, "day_pre")

        with col2:
            st.markdown("**Night Shift**")
            night_pre = _render(night_staff, NIGHT_SHIFTS, "night_pre")

    return {**day_pre, **night_pre}


# ---------------------------------------------------------------------------
# Control buttons
# ---------------------------------------------------------------------------

def control_buttons() -> Tuple[bool, bool]:
    col1, col2 = st.columns(2)
    with col1:
        generate = st.button("▶ Generate Roster", type="primary", use_container_width=True)
    with col2:
        clear = st.button("✖ Clear & Start Over", use_container_width=True)
        if clear:
            st.session_state.clear_staff_inputs = True
            st.session_state.staff_assignments  = {}
            st.rerun()
    return generate, clear


def clear_inputs():
    st.session_state.staff_assignments = {}


# ---------------------------------------------------------------------------
# PRIMARY RESULT: Staff assignment tables  (top of results, always visible)
# ---------------------------------------------------------------------------

def display_staff_view_primary(
    day_view,
    night_view,
):
    """
    The main output — name/shift tables shown immediately at the top.
    day_view and night_view are DataFrames or None.
    """
    st.subheader("Shift Assignments")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Day Shift**")
        if day_view is not None and not day_view.empty:
            st.dataframe(
                day_view.rename(columns={"STAFF NAME": "Name", "Assignment": "Shift"}),
                hide_index=True,
                use_container_width=True,
                height=min(50 + len(day_view) * 35, 700),
            )
        else:
            st.info("No day shift staff entered.")

    with col2:
        st.markdown("**Night Shift**")
        if night_view is not None and not night_view.empty:
            st.dataframe(
                night_view.rename(columns={"STAFF NAME": "Name", "Assignment": "Shift"}),
                hide_index=True,
                use_container_width=True,
                height=min(50 + len(night_view) * 35, 700),
            )
        else:
            st.info("No night shift staff entered.")

    # Download the combined table
    combined_rows = []
    if day_view is not None and not day_view.empty:
        tmp = day_view.copy()
        tmp.insert(0, "Period", "Day")
        combined_rows.append(tmp)
    if night_view is not None and not night_view.empty:
        tmp = night_view.copy()
        tmp.insert(0, "Period", "Night")
        combined_rows.append(tmp)

    if combined_rows:
        combined = pd.concat(combined_rows, ignore_index=True)
        st.download_button(
            "Download assignments (CSV)",
            data=combined.to_csv(index=False).encode("utf-8"),
            file_name="assignments.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# SECONDARY RESULTS: everything else, collapsed
# ---------------------------------------------------------------------------

def display_unassigned_staff(unassigned: List[Tuple[str, str]], shift_type: str = ""):
    if unassigned:
        label = f"Unassigned Staff — {shift_type} ({len(unassigned)})"
        with st.expander(label, expanded=True):
            for name, reason in unassigned:
                st.write(f"- **{name}**: {reason}")


def display_staffing_metrics(metrics: Dict, title: str = "Staffing Metrics"):
    with st.expander(title, expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Staff",     metrics["total_staff"])
        c2.metric("No-Matrix Staff", metrics["no_matrix_count"])
        c3.metric("ACTUAL Shifts",   metrics.get("final_actual", metrics.get("actual", 0)))
        st.markdown("---")
        st.write(
            f"**Nurses:** {metrics['nurse_count']}  |  "
            f"**Medics:** {metrics['medic_count']}  |  "
            f"**Dual:** {metrics['dual_count']}"
        )
        st.write(f"**ZENITH** (staff / 2): {metrics['zenith']}")
        st.write(f"**ACTUAL** (min of ZENITH, No-Matrix): {metrics['actual']}")
        if "balanced_nurse_count" in metrics:
            st.write(
                f"**After dual balancing** — Nurses: {metrics['balanced_nurse_count']}, "
                f"Medics: {metrics['balanced_medic_count']}, "
                f"Final ACTUAL: {metrics['final_actual']}"
            )


def display_dual_assignments(dual_assignments: Dict[str, str], title: str = "Dual Staff Role Assignments"):
    if not dual_assignments:
        return
    with st.expander(title, expanded=False):
        for name, role in dual_assignments.items():
            st.write(f"- **{name}** functioning as **{role}**")


def display_shift_view(
    shift_assignments: Dict[str, List],
    shifts_dict: Dict,
    title: str = "Shift View",
):
    with st.expander(title, expanded=False):
        for shift_name, info in sorted(shifts_dict.items(), key=lambda x: x[1]["rank"]):
            staff_on_shift = shift_assignments.get(shift_name, [])
            st.markdown(
                f"**{shift_name}** — "
                f"{info['start_time'][:2]}:{info['start_time'][2:]}–"
                f"{info['end_time'][:2]}:{info['end_time'][2:]}"
            )
            if staff_on_shift:
                for name, role, nm in staff_on_shift:
                    nm_tag = " No Matrix" if nm == 1 else ""
                    st.write(f"  • {name} ({role}{nm_tag})")
            else:
                st.write("  • Not staffed")


def display_combined_roster(
    day_assignments: Dict[str, List],
    night_assignments: Dict[str, List],
    day_processed: bool = True,
    night_processed: bool = True,
):
    with st.expander("Full Combined Roster Table", expanded=False):
        rows = []
        if day_processed:
            for sn, info in sorted(DAY_SHIFTS.items(), key=lambda x: x[1]["rank"]):
                staff = day_assignments.get(sn, [])
                rows.append({
                    "Shift": sn, "Type": "Day",
                    "Start": info["start_time"], "End": info["end_time"],
                    "Staff": ", ".join(f"{s[0]} ({s[1]})" for s in staff) or "Not Staffed",
                })
        if night_processed:
            for sn, info in sorted(NIGHT_SHIFTS.items(), key=lambda x: x[1]["rank"]):
                staff = night_assignments.get(sn, [])
                rows.append({
                    "Shift": sn, "Type": "Night",
                    "Start": info["start_time"], "End": info["end_time"],
                    "Staff": ", ".join(f"{s[0]} ({s[1]})" for s in staff) or "Not Staffed",
                })
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, hide_index=True, use_container_width=True)
            st.download_button(
                "Download full roster (CSV)",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="full_roster.csv",
                mime="text/csv",
            )


# ---------------------------------------------------------------------------
# Staffing Calculator tab
# ---------------------------------------------------------------------------

def staffing_calculator_section() -> Tuple[str, bool]:
    st.subheader("Quick Staffing Calculator")
    st.markdown(
        "Paste names with **D** or **N** to calculate ACTUAL metrics "
        "without generating a full roster:\n\n"
        "```\nSmith J.    D\nGarcia M.   D\nBell P.     N\n```"
    )
    calc_input = st.text_area(
        "Staff list (name + D/N)",
        height=300,
        key="calculator_input",
        placeholder="Smith J.    D\nGarcia M.   N",
    )
    calc_button = st.button("Calculate", type="primary")
    return calc_input, calc_button


def display_calculator_results(
    day_actual: int,
    night_actual: int,
    total_actual: int,
    day_metrics: Dict = None,
    night_metrics: Dict = None,
):
    st.subheader("Results")
    c1, c2, c3 = st.columns(3)
    c1.metric("Day ACTUAL",   day_actual)
    c2.metric("Night ACTUAL", night_actual)
    c3.metric("Total ACTUAL", total_actual)

    if day_metrics or night_metrics:
        st.divider()
        d1, d2 = st.columns(2)

        def _detail(col, m, label):
            with col:
                if m:
                    with st.expander(f"{label} Details", expanded=False):
                        st.write(f"Total: **{m.get('total_staff', 0)}** staff")
                        st.write(
                            f"Nurses: {m.get('nurse_count', 0)} | "
                            f"Medics: {m.get('medic_count', 0)} | "
                            f"Dual: {m.get('dual_count', 0)}"
                        )
                        st.write(f"No-Matrix: {m.get('no_matrix_count', 0)}")
                        st.write(f"ZENITH: {m.get('zenith', 0)}")
                        if "balanced_nurse_count" in m:
                            st.write(
                                f"After balancing — Nurses: {m['balanced_nurse_count']}, "
                                f"Medics: {m['balanced_medic_count']}"
                            )
                else:
                    st.info(f"No {label.lower()} staff.")

        _detail(d1, day_metrics,   "Day")
        _detail(d2, night_metrics, "Night")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Two-Week Scheduler tab
# ---------------------------------------------------------------------------

def two_week_scheduler_section():
    """Upload widget and instructions for the two-week scheduler."""
    st.subheader("Two-Week Schedule Builder")
    st.markdown(
        "Upload your two-week schedule template (the Excel file with staff rows and 14 date columns). "
        "The tool will read who is working **D** or **N** each day, apply all rest, "
        "consecutive-shift, and preference rules, and produce a completed schedule."
    )

    uploaded = st.file_uploader(
        "Upload schedule template (.xlsx)",
        type=["xlsx"],
        key="two_week_upload",
        label_visibility="collapsed",
    )
    run_btn = st.button("▶ Build Schedule", type="primary",
                        disabled=(uploaded is None),
                        key="two_week_run")
    return uploaded, run_btn


def display_two_week_results(summary: Dict, sheet_name: str, excel_bytes: bytes):
    """Show summary metrics and per-day breakdown, then offer the download."""
    st.success(
        f"✅ Schedule built from sheet **{sheet_name}** — "
        f"{summary['filled_slots']} shifts assigned, "
        f"{summary['open_slots']} open needs, "
        f"fill rate **{summary['fill_rate']}**"
    )

    st.download_button(
        "⬇ Download completed schedule (Excel)",
        data=excel_bytes,
        file_name=f"schedule_{sheet_name.replace(' ', '_')}_assigned.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("---")
    st.markdown("### Day-by-day summary")

    for day in summary['days']:
        has_open = day['day_open'] > 0 or day['night_open'] > 0
        label = (
            f"{'⚠️' if has_open else '✅'} **{day['date']}** — "
            f"Day: {day['day_filled']} filled / {day['day_open']} open  |  "
            f"Night: {day['night_filled']} filled / {day['night_open']} open"
        )
        with st.expander(label, expanded=has_open):
            dc, nc = st.columns(2)
            with dc:
                st.markdown("**Day Shifts**")
                for shift_code, name in sorted(day['day_shifts'].items()):
                    if name:
                        st.write(f"• {shift_code}: {name}")
                    else:
                        st.markdown(f"• **{shift_code}: OPEN** 🔴")
            with nc:
                st.markdown("**Night Shifts**")
                for shift_code, name in sorted(day['night_shifts'].items()):
                    if name:
                        st.write(f"• {shift_code}: {name}")
                    else:
                        st.markdown(f"• **{shift_code}: OPEN** 🔴")
