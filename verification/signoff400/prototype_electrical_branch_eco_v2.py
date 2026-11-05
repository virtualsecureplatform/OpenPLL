"""Add measured residual D-pin hold repairs to the electrical branch ECO."""
from prototype_electrical_branch_eco import actions_for_plan as electrical
from prototype_measured_path_eco import buffer_actions

def actions_for_plan(plan):
    targets=plan.get('short_data_targets',[])
    if any(t.get('capture_pin')!='D' or t.get('buffers')!=1 or not t.get('capture_master','').startswith('sky130_fd_sc_hs__dfrtp_') for t in targets):raise ValueError('bounded measured FF D-pin repairs required')
    return electrical(plan)+(buffer_actions(targets).replace('prototype_path_closure_', 'prototype_electrical_residual_hold_') if targets else '')
