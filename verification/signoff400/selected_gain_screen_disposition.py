"""Classify covered functional evidence separately from incomplete execution."""

def classify(report):
    state=report.get('state')
    if state=='needs_native_tuning_points':
        if not report.get('measurement_requests'):raise ValueError('missing-coverage state without measurement requests')
        return 'indeterminate_lookup'
    if report.get('native_exit')!=0 or report.get('terminal_marker_present')is not True or report.get('reference_phase_coverage_pass')is not True:
        raise ValueError('incomplete execution or phase stimulus; gain rejection forbidden')
    if report.get('measurement_requests'):raise ValueError('covered case has measurement requests')
    if state=='diagnostic_simulation_completed'and report.get('functional_trace_pass')is True:return 'pass_screen'
    if state=='diagnostic_failed'and report.get('functional_trace_pass')is False:return 'functional_failure'
    raise ValueError('inconsistent diagnostic disposition')
