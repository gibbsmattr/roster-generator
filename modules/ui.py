"""
Streamlit UI components for the Roster Generator.

Layout priority:
  1. Staff assignment tables — shown immediately, full width, at the top of results
  2. Everything else (metrics, shift view, logs) — collapsed by default
"""

import streamlit as st
import pandas as pd
import urllib.request
from typing import Dict, List, Tuple

from modules.config import DAY_SHIFTS, NIGHT_SHIFTS, ORG_NAME, PAGE_LAYOUT, PAGE_ICON

# ---------------------------------------------------------------------------
# GitHub preferences URL — update this to point to your raw file
# ---------------------------------------------------------------------------
GITHUB_PREFS_URL = (
    "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/Preferences/preferences.xlsx"
)

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

_CUSTOM_CSS = """
<style>
/* ── Global typography & background ─────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* Subtle dark-navy header bar */
[data-testid="stHeader"] {
    background: #0f172a;
}

/* App background — very light blue-grey */
.stApp {
    background-color: #f1f5f9;
}

/* ── Main content card feel ─────────────────────────────────────────── */
section[data-testid="stMain"] > div {
    padding-top: 1.2rem;
}

/* ── Title ──────────────────────────────────────────────────────────── */
h1 {
    color: #0f172a !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px;
    font-size: 1.9rem !important;
    border-bottom: 3px solid #3b82f6;
    padding-bottom: 0.4rem;
    margin-bottom: 1rem !important;
}

/* ── Subheadings ────────────────────────────────────────────────────── */
h2, h3 {
    color: #1e3a5f !important;
    font-weight: 600 !important;
}

/* ── Tabs ───────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] {
    font-weight: 600;
    font-size: 0.92rem;
    color: #475569;
    padding: 0.5rem 1.1rem;
    border-radius: 6px 6px 0 0;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #1d4ed8 !important;
    border-bottom: 3px solid #3b82f6 !important;
    background: #eff6ff;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
/* Generate / primary → blue */
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.55rem 1.4rem !important;
    box-shadow: 0 2px 6px rgba(37,99,235,0.35) !important;
    transition: all 0.15s ease !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1d4ed8, #1e40af) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.45) !important;
    transform: translateY(-1px) !important;
}

/* Clear / secondary → red */
div.stButton > button[kind="secondary"] {
    background: white !important;
    color: #dc2626 !important;
    border: 2px solid #dc2626 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.55rem 1.4rem !important;
    transition: all 0.15s ease !important;
}
div.stButton > button[kind="secondary"]:hover {
    background: #fef2f2 !important;
    box-shadow: 0 2px 8px rgba(220,38,38,0.2) !important;
    transform: translateY(-1px) !important;
}

/* ── Expanders ──────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: white;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
[data-testid="stExpander"] summary {
    font-weight: 600;
    color: #1e3a5f;
    padding: 0.6rem 1rem;
}

/* ── Text areas ─────────────────────────────────────────────────────── */
textarea {
    border-radius: 8px !important;
    border: 1.5px solid #cbd5e1 !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
    font-size: 0.85rem !important;
    background: #fafcff !important;
}
textarea:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

/* ── DataFrames / tables ─────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

/* ── Metrics ────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: white;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
[data-testid="stMetricLabel"] { color: #64748b !important; font-weight: 500 !important; }
[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 700 !important; }

/* ── Info / warning / success banners ──────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #1e3a5f !important;
}
[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

/* ── Status / badge chips for prefs source ──────────────────────────── */
.prefs-badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-left: 0.5rem;
}
.badge-github { background: #dcfce7; color: #15803d; }
.badge-upload { background: #dbeafe; color: #1d4ed8; }
.badge-none   { background: #fee2e2; color: #dc2626; }
</style>
"""

def setup_page():
    st.set_page_config(page_title=ORG_NAME, layout=PAGE_LAYOUT, page_icon=PAGE_ICON)
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)
    st.title(f"{PAGE_ICON} {ORG_NAME}")
    st.caption("Version 11.7 - Fixed: All 14 Days, No 'None', Proper Dropdowns")


# ---------------------------------------------------------------------------
# Preferences loading (GitHub auto-fetch + manual upload fallback)
# ---------------------------------------------------------------------------

def _try_load_github_prefs() -> pd.DataFrame | None:
    """Attempt to fetch the preferences file from GitHub. Returns None on failure."""
    try:
        from modules import data_manager
        import io
        req = urllib.request.Request(
            GITHUB_PREFS_URL,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read()
        df = data_manager.load_staff_data(io.BytesIO(raw))
        return df
    except Exception:
        return None


def render_preferences_section():
    """
    Preferences loader shown above the tabs.
    Priority order:
    1. Check for local file in Preferences/preferences.xlsx
    2. Try to fetch from GitHub
    3. Manual upload option
    Manual upload always wins if the user provides a file.
    """
    from modules import data_manager
    import os

    # ── Auto-load from local file or GitHub on startup ──────────────────────
    if st.session_state.get("staff_data_cache") is None and \
       st.session_state.get("prefs_source") is None:
        
        # First, try local file in Preferences folder
        local_path = "Preferences/preferences.xlsx"
        if os.path.exists(local_path):
            try:
                df = data_manager.load_staff_data_from_path(local_path)
                st.session_state.staff_data_cache = df
                st.session_state.prefs_source = "local"
                st.session_state.uploaded_filename = "preferences.xlsx (Local)"
            except Exception as e:
                st.warning(f"Found local preferences file but couldn't load it: {e}")
        
        # If no local file, try GitHub
        if st.session_state.get("staff_data_cache") is None:
            with st.spinner("Loading staff preferences from GitHub…"):
                df = _try_load_github_prefs()
            if df is not None:
                st.session_state.staff_data_cache = df
                st.session_state.prefs_source = "github"
                st.session_state.uploaded_filename = "preferences.xlsx (GitHub)"

    # ── Status badge ─────────────────────────────────────────────────────────
    source = st.session_state.get("prefs_source")
    fname  = st.session_state.get("uploaded_filename", "")

    if source == "local":
        badge = '<span class="prefs-badge badge-github">✓ Local File</span>'
        status_msg = f"Staff preferences loaded from local file {badge}"
    elif source == "github":
        badge = '<span class="prefs-badge badge-github">✓ GitHub</span>'
        status_msg = f"Staff preferences loaded from GitHub {badge}"
    elif source == "upload":
        badge = '<span class="prefs-badge badge-upload">✓ Uploaded</span>'
        status_msg = f"Staff preferences loaded: **{fname}** {badge}"
    else:
        badge = '<span class="prefs-badge badge-none">⚠ Not loaded</span>'
        status_msg = f"No preferences file loaded {badge}"

    with st.expander(
        f"📋 Staff Preferences File — {'loaded' if source else 'not loaded'}",
        expanded=(source is None),
    ):
        st.markdown(status_msg, unsafe_allow_html=True)

        if source == "local":
            st.caption("Source: `Preferences/preferences.xlsx` (in repository)")
        elif source == "github":
            st.caption(f"Source: `{GITHUB_PREFS_URL}`")

        st.markdown("**Upload a new preferences file** (replaces current):")
        uploaded = st.file_uploader(
            "Upload preferences (.xlsx)",
            type=["xlsx"],
            key="prefs_uploader",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            try:
                df = data_manager.load_staff_data(uploaded)
                st.session_state.staff_data_cache = df
                st.session_state.prefs_source = "upload"
                st.session_state.uploaded_filename = uploaded.name
                st.success(f"Loaded **{uploaded.name}** — {len(df)} staff members.")
            except Exception as e:
                st.error(f"Failed to load file: {e}")

        if source is not None:
            n = len(st.session_state.staff_data_cache)
            st.caption(f"{n} staff members currently loaded.")


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
    col1, col2 = st.columns([3, 1])
    with col1:
        generate = st.button("▶ Generate Roster", type="primary", use_container_width=True)
    with col2:
        clear = st.button("✖ Clear & Reset", type="secondary", use_container_width=True)
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

def grid_scheduler_section() -> Tuple[str, bool, bool]:
    """Paste-grid interface for the two-week scheduler."""
    st.subheader("Two-Week Schedule Builder")

    with st.expander("📋 How to use this", expanded=False):
        st.markdown("""
**Step 1** — In your Excel template, select the **Name column** plus the **16 day columns**
(2 prior days + 14 current days). Copy them.

**Step 2** — Paste into the box below. Each row should be tab-separated, exactly as Excel copies it.

**Step 3** — Hit **Build Schedule**. The app will fill every bare **D** or **N** cell with a
specific shift code based on each person's preferences, rest rules, and consecutive-shift limits.

**Step 4** — Copy the output grid and paste it back into Excel.

---
**What counts as a bare D or N (will be assigned):**
`D`, `N`, `D/N`, `D*`, `*D`, `D#`, `#D`, `ON D`, `D1*`, `D2*`, `D3*`

**What is left alone (already assigned):**
Any specific shift code like `D7B`, `N9L`, `MG`, etc.

**What is skipped (non-working — not counted toward consecutive limits):**
`LT`, `LT-D`, `LT-N`, `SM`, `SIM`, `AT`, `Clinical`, `LOA`, blank cells, etc.
""")

    pasted = st.text_area(
        "Paste your schedule grid here (name + 16 columns, tab-separated)",
        height=320,
        key="grid_paste",
        placeholder="Smith J.\tN7P\tN7P\tD\tD\t\tN\tN\t...\nGarcia M.\tD7B\t\tD\tD\tN\tN\t\t...",
    )

    night_only = st.checkbox(
        "🌙 Night shifts only (leave all D markers unassigned)",
        value=False,
        key="night_only_checkbox",
        help="When checked, only N markers will be assigned. D markers will be left as-is."
    )

    run_btn = st.button(
        "▶ Build Schedule",
        type="primary",
        disabled=not bool(pasted and pasted.strip()),
        key="grid_run",
    )
    return pasted, run_btn, night_only


def display_grid_results(names: List[str], output_grid: List[List[str]],
                          warnings: List[str], stats: Dict):
    """Show stats, warnings, copyable output grid, and a visual table."""

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Staff rows", stats.get("total_staff", 0))
    c2.metric("Shifts assigned", stats.get("assigned", 0))
    c3.metric("Left unresolved", stats.get("unresolved", 0))
    c4.metric("Unknown names", stats.get("unknown_names", 0))

    if warnings:
        with st.expander(f"⚠️ {len(warnings)} warning(s)", expanded=False):
            for w in warnings:
                st.write(f"• {w}")

    st.markdown("---")
    st.markdown("### Output grid — copy this back into Excel")
    st.caption(
        "Select all text below (Ctrl+A / Cmd+A inside the box), copy, "
        "then paste into the matching cells in Excel."
    )

    lines = []
    for name, row in zip(names, output_grid):
        lines.append(name + "\t" + "\t".join(row))
    grid_text = "\n".join(lines)

    st.text_area(
        "Output (tab-separated, paste into Excel)",
        value=grid_text,
        height=340,
        key="grid_output",
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### Visual check — current 14 days")
    st.caption("Prior 2 days not shown. Click cells to edit from dropdown, then hit 'Re-run with edits' to recalculate.")

    from modules.grid_scheduler import DAY_CODES, NIGHT_CODES
    from modules.config import ALL_SHIFTS as _AS
    from datetime import datetime, timedelta

    # Dropdown options in specific order
    dropdown_options = ["", "D", "N", "D/N", 
                       "D7B", "D7P", "D9L", "D11M", "D11H", "MG", "GR", "LG", "PG", "FLOAT",
                       "N7B", "N7P", "N9L", "NG", "NP",
                       "OFF", "LT", "LT-D", "LT-N", "AT", "SM", "Clinical", "LOA"]
    
    # Day names cycle through the week, starting Sunday
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    
    # Build column headers for all 14 days (make unique with day number)
    column_headers = []
    for i in range(14):
        day_name = day_names[i % 7]
        column_headers.append(f"{day_name}_{i+1}")  # Sun_1, Mon_2, etc. for uniqueness
    
    table_rows = []
    for name, row in zip(names, output_grid):
        current = row[2:]  # Skip prior 2 days
        row_dict = {"Name": name}
        for i in range(14):
            val = current[i].strip() if current[i] else ""
            # Replace None or empty with actual empty string
            if val == "None" or not val:
                val = ""
            row_dict[column_headers[i]] = val
        table_rows.append(row_dict)

    df = pd.DataFrame(table_rows)
    
    # Configure columns
    column_config = {
        "Name": st.column_config.TextColumn("Name", width="small")  # Changed to small
    }
    
    # Add config for each of the 14 day columns
    for i, col_header in enumerate(column_headers):
        display_name = day_names[i % 7]  # Just show the day name without number
        column_config[col_header] = st.column_config.SelectboxColumn(
            display_name,  # Display name (Sun, Mon, etc.)
            width="small",
            options=dropdown_options,
            required=False
        )
    
    # Use data_editor for editable table
    edited_df = st.data_editor(
        df, 
        hide_index=True, 
        use_container_width=True,
        height=min(60 + len(names)*35, 700),
        key="editable_schedule",
        column_config=column_config,
        disabled=["Name"]  # Make Name column non-editable
    )
    
    # Add re-run button
    col1, col2 = st.columns([1, 4])
    with col1:
        rerun_btn = st.button("🔄 Re-run with edits", type="secondary", key="rerun_with_edits")
    
    if rerun_btn:
        # Convert edited dataframe back to paste format
        new_paste_lines = []
        for idx, (name, orig_row) in enumerate(zip(names, output_grid)):
            # Get prior 2 days from original
            prior_2 = orig_row[0:2]
            # Get edited 14 days from dataframe
            edited_row_data = edited_df.iloc[idx]
            edited_14_days = []
            for col_header in column_headers:
                val = edited_row_data[col_header]
                # Convert None or nan to empty string
                if pd.isna(val) or val == "None" or val is None or str(val).strip() == "":
                    val = ""
                else:
                    val = str(val).strip()
                edited_14_days.append(val)
            # Combine
            full_row = prior_2 + edited_14_days
            new_paste_lines.append(name + "\t" + "\t".join(full_row))
        
        new_paste_text = "\n".join(new_paste_lines)
        
        # Store in session state to trigger re-run
        st.session_state.grid_paste = new_paste_text
        st.session_state.rerun_requested = True
        st.rerun()


def two_week_scheduler_section():
    """DEPRECATED — redirects to grid_scheduler_section."""
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


# ---------------------------------------------------------------------------
# Two-Week Paste Scheduler tab
# ---------------------------------------------------------------------------

def two_week_paste_section():
    """UI for the paste-grid two-week scheduler."""
    st.markdown(
        "Copy a rectangle of cells directly from your Excel template and paste below. "
        "The app fills in every **D** and **N** cell with a specific shift code, "
        "then gives you the completed grid to paste straight back."
    )
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Paste 1 — Schedule Grid**")
        st.caption("Select: Name column + 2 prior-period cols + 14 working-day cols → Cmd+C → paste here")
        grid_text = st.text_area(
            "grid", height=420, key="paste_grid_input",
            placeholder="Gallagher\t\t\t\t\tSM\tN7P\tN7P ...",
            label_visibility="collapsed",
        )
    with col2:
        st.markdown("**Paste 2 — Staff Metadata**")
        st.caption("Select: Name, Matrix, Flex, 10h Turn, Wk1, Wk2, B, H, L, P, M, B, L, P → Cmd+C → paste here (include header row)")
        meta_text = st.text_area(
            "meta", height=420, key="paste_meta_input",
            placeholder="Name\tMatrix\tFlex\t10h Turn\tWk1\tWk2\tB\tH\tL\tP\tM\tB\tL\tP\nGallagher\ta\tYes\t\t3\t3\t2\t5\t3\t1\t3\t2\t3\t1",
            label_visibility="collapsed",
        )

    st.markdown("**Start date of the 14-day window** (used for column headers only)")
    from datetime import date as date_cls
    start_date_val = st.date_input("start", key="paste_start_date", label_visibility="collapsed")

    c1, c2 = st.columns([3, 1])
    with c1:
        run_btn = st.button(
            "▶ Generate Schedule", type="primary",
            use_container_width=True, key="paste_run_btn",
            disabled=(not grid_text.strip()),
        )
    with c2:
        if st.button("✖ Clear", type="secondary", use_container_width=True, key="paste_clear_btn"):
            for k in ("paste_grid_input", "paste_meta_input"):
                st.session_state.pop(k, None)
            st.rerun()

    return grid_text, meta_text, start_date_val, run_btn


def display_paste_results(output_grid: str, summary: Dict):
    """Show summary stats and the completed grid ready to copy back to Excel."""
    if summary["open"] == 0:
        st.success(f"✅ All {summary['filled']} shifts assigned — fill rate {summary['fill_rate']}")
    else:
        st.warning(
            f"⚠️ {summary['filled']} shifts assigned, **{summary['open']} still open** "
            f"— fill rate {summary['fill_rate']}"
        )
    if summary["meta_matched"] < summary["staff_count"]:
        unmatched = summary["staff_count"] - summary["meta_matched"]
        st.info(
            f"ℹ️ {unmatched} staff member(s) had no metadata match — skipped. "
            "Check that names in both pastes match exactly."
        )
    st.markdown(f"**{summary['staff_count']} staff** · "
                f"**{summary['meta_matched']} with metadata**")
    st.divider()
    st.markdown("### Completed grid — select all and paste back into Excel")
    st.caption("Click inside the box → Cmd+A → Cmd+C")
    st.text_area(
        "output", value=output_grid, height=520,
        key="paste_output_area", label_visibility="collapsed",
    )
