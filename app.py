"""Staff Roster Generator — Main Application. Run with: streamlit run app.py"""
import streamlit as st
from modules import ui, data_manager
from modules.roster_generator import RosterGenerator
from modules.config import DAY_SHIFTS, NIGHT_SHIFTS
from modules.logging_manager import get_logger

for key, default in [
    ("day_staff_input",""),("night_staff_input",""),
    ("clear_staff_inputs",False),("staff_data_cache",None),
    ("uploaded_filename",None),("prefs_source",None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.clear_staff_inputs:
    st.session_state.day_staff_input = ""
    st.session_state.night_staff_input = ""
    st.session_state.clear_staff_inputs = False

ui.setup_page()
logger = get_logger()
ui.render_preferences_section()

def process_shifts(staff_list, shift_type, shifts_dict, staff_data, prior_shifts, pre_assigned):
    is_day = shift_type == "Day"
    filtered = staff_data[staff_data["STAFF NAME"].isin(staff_list)].copy()
    metrics = data_manager.calculate_staffing_metrics(filtered)
    dual_assignments = data_manager.balance_dual_staff(filtered, metrics)
    metrics = data_manager.recalculate_balanced_metrics(metrics, dual_assignments)
    generator = RosterGenerator(filtered, prior_shifts, pre_assigned, metrics, dual_assignments, is_day_shift=is_day)
    shift_assignments = generator.generate_roster()
    staff_view = generator.create_staff_view(staff_list)
    return shift_assignments, staff_view, generator, metrics, dual_assignments

tab1, tab2, tab3 = st.tabs(["Roster Generator", "Staffing Calculator", "Two-Week Scheduler"])

with tab1:
    day_input, night_input = ui.staff_input_section()
    day_list, day_prior = data_manager.parse_staff_input(day_input)
    night_list, night_prior = data_manager.parse_staff_input(night_input)
    prior_shifts = {**day_prior, **night_prior}
    pre_assigned = ui.pre_assignment_section(day_list, night_list)
    generate_btn, clear_btn = ui.control_buttons()
    if clear_btn:
        logger.clear_logs(); ui.clear_inputs(); st.rerun()
    if generate_btn:
        logger.clear_logs()
        if st.session_state.staff_data_cache is None:
            st.error("Please load a staff preferences file first (see the panel above).")
        elif not day_list and not night_list:
            st.warning("Paste at least one staff name to get started.")
        else:
            try:
                staff_data = st.session_state.staff_data_cache
                do_day, do_night = bool(day_list), bool(night_list)
                day_assignments = night_assignments = {}
                day_view = night_view = day_gen = night_gen = None
                day_metrics = night_metrics = None
                day_dual = night_dual = {}
                if do_day:
                    day_assignments, day_view, day_gen, day_metrics, day_dual = process_shifts(day_list, "Day", DAY_SHIFTS, staff_data, prior_shifts, pre_assigned)
                if do_night:
                    night_assignments, night_view, night_gen, night_metrics, night_dual = process_shifts(night_list, "Night", NIGHT_SHIFTS, staff_data, prior_shifts, pre_assigned)
                st.divider()
                ui.display_staff_view_primary(day_view, night_view)
                if do_day and day_gen: ui.display_unassigned_staff(day_gen.get_unassigned_staff(), "Day")
                if do_night and night_gen: ui.display_unassigned_staff(night_gen.get_unassigned_staff(), "Night")
                st.markdown("##### More Details")
                if do_day:
                    ui.display_staffing_metrics(day_metrics, "Day Staffing Metrics")
                    ui.display_dual_assignments(day_dual, "Day Dual Staff Assignments")
                    ui.display_shift_view(day_assignments, DAY_SHIFTS, "Day Shift View")
                if do_night:
                    ui.display_staffing_metrics(night_metrics, "Night Staffing Metrics")
                    ui.display_dual_assignments(night_dual, "Night Dual Staff Assignments")
                    ui.display_shift_view(night_assignments, NIGHT_SHIFTS, "Night Shift View")
                if do_day or do_night:
                    ui.display_combined_roster(day_assignments, night_assignments, do_day, do_night)
                logger.display_logs_ui("Assignment Process Logs")
            except Exception as exc:
                import traceback; st.error(f"Error: {exc}"); st.error(traceback.format_exc())

with tab3:
    from modules.grid_scheduler import run_grid_scheduler
    pasted_grid, run_grid = ui.grid_scheduler_section()
    if run_grid and pasted_grid:
        if st.session_state.staff_data_cache is None:
            st.error("Please load a staff preferences file first (see the panel above).")
        else:
            with st.spinner("Building schedule..."):
                try:
                    names, output_grid, warnings, stats = run_grid_scheduler(
                        pasted_grid, st.session_state.staff_data_cache
                    )
                    ui.display_grid_results(names, output_grid, warnings, stats)
                except Exception as exc:
                    import traceback; st.error(f"Error: {exc}"); st.error(traceback.format_exc())

with tab2:
    calc_input, calc_btn = ui.staffing_calculator_section()
    if calc_btn:
        if st.session_state.staff_data_cache is None:
            st.error("Please load a staff preferences file first.")
        else:
            try:
                day_calc, night_calc = data_manager.parse_calculator_input(calc_input)
                staff_data = st.session_state.staff_data_cache
                day_actual = night_actual = 0; day_metrics = night_metrics = None
                if day_calc:
                    dm = data_manager.calculate_staffing_metrics(staff_data[staff_data["STAFF NAME"].isin(day_calc)].copy())
                    da = data_manager.balance_dual_staff(staff_data[staff_data["STAFF NAME"].isin(day_calc)].copy(), dm)
                    dm = data_manager.recalculate_balanced_metrics(dm, da)
                    day_actual, day_metrics = dm.get("final_actual", 0), dm
                if night_calc:
                    nm = data_manager.calculate_staffing_metrics(staff_data[staff_data["STAFF NAME"].isin(night_calc)].copy())
                    na = data_manager.balance_dual_staff(staff_data[staff_data["STAFF NAME"].isin(night_calc)].copy(), nm)
                    nm = data_manager.recalculate_balanced_metrics(nm, na)
                    night_actual, night_metrics = nm.get("final_actual", 0), nm
                ui.display_calculator_results(day_actual, night_actual, day_actual + night_actual, day_metrics, night_metrics)
            except Exception as exc:
                import traceback; st.error(f"Error: {exc}"); st.error(traceback.format_exc())
