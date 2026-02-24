# Staff Roster Generator

A Streamlit-based scheduling tool for critical care transport operations (ambulance & helicopter).

Automatically assigns staff to shifts based on role (nurse/medic/dual), seniority,
shift preferences, rest requirements, and conflict rules.

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Setup

### Staff data file

Upload your `.xlsx` file directly in the app using the **"Staff Data Source"** uploader at the top of the page. No folders or file paths needed — just drag and drop. The file stays loaded for your whole session.

Required columns:

| Column | Description |
|--------|-------------|
| `STAFF NAME` | Full name as it will appear on the roster |
| `ROLE` | `nurse`, `medic`, or `dual` |
| `Seniority` | Numeric rank — lower number = more senior (1 = most senior) |
| `No Matrix` | `1` if this person can be a "No Matrix" staff member, else `0` |
| `Reduced Rest OK` | `1` if this person accepts reduced (10h) rest periods, else `0` |

**Shift preference columns** — use base names that match `BASE_TO_SHIFTS` keys in `config.py`
(e.g. `DAY_KBED`, `NIGHT_KLWM`).  Enter a numeric preference rank: `1` = first choice,
`2` = second choice, etc.  Leave blank or `0` for no preference.

---

## Customising for your organisation

All organisation-specific settings live in **`modules/config.py`**:

- **`DAY_SHIFTS` / `NIGHT_SHIFTS`** — define your shift codes, times, and priority order.
- **`BASE_TO_SHIFTS`** — map base/location names (Excel column headers) to shift codes.
- **`STAFF_CONFLICTS`** — pairs of staff who cannot share a shift.
- **`STAFF_SHIFT_RESTRICTIONS`** — restrict individual staff to specific shifts.
- **`ORG_NAME`** / **`PAGE_ICON`** — branding shown in the browser tab and page header.

---

## How the algorithm works

1. **PRE-ASSIGNMENT** — Any staff manually locked to a shift in the UI are placed first.
2. **TRUMP passes** — If only one person can fill a role on a shift, they are assigned
   immediately. This repeats until no more forced assignments exist.
3. **VALHALLA pass** — Remaining staff are processed in seniority order.  Each person is
   placed on their highest-preference eligible shift; if no preference data is available,
   they go to the first eligible shift that needs their role.

After each VALHALLA placement, TRUMP passes run again to catch newly forced assignments.

### Key terms

| Term | Meaning |
|------|---------|
| **ZENITH** | Maximum possible shifts = total staff ÷ 2 |
| **ACTUAL** | Shifts that can realistically be staffed = min(ZENITH, No-Matrix count) |
| **BALLS** | Shifts that may legally have two No-Matrix staff = No-Matrix count − ACTUAL |
| **No Matrix** | Staff qualified to lead a shift without a "matrix" requirement |
| **Dual** | Staff certified as both nurse and medic |

---

## File layout

```
app.py                      ← Entry point
requirements.txt
Preferences/
    your_staff_data.xlsx    ← Place ONE file here
modules/
    __init__.py
    config.py               ← ★ Edit this to configure for your org
    data_manager.py         ← Excel loading, input parsing, metrics
    shift_utils.py          ← Rest checks, eligibility logic
    roster_generator.py     ← Core assignment algorithm
    logging_manager.py      ← Structured logging + UI display
    ui.py                   ← All Streamlit widgets and output rendering
```
