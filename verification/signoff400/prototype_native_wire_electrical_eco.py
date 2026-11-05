"""Use characterized cells for electrical repair while freezing CDC first stages."""


def actions_for_plan(plan):
    cells=plan['protected_first_stage_cells']
    if (len(cells)!=13 or len(set(cells))!=13 or plan.get('targets') or plan.get('branches')
            or plan['repair_kind']!='native_library_slew_and_capacitance'
            or plan['setup_frequency_optimization_requested'] is not False):
        raise ValueError('bounded electrical-only repair and thirteen protected first stages required')
    if any(any(c in name for c in '{}\\\n\r') for name in cells):raise ValueError('invalid protected instance')
    path=plan['maximum_wire_spef']
    if any(c in path for c in '{}\n\r'):raise ValueError('invalid RC path')
    text=''
    for name in cells:
        text+=f'''set protected [$block findInst {{{name}}}]
if {{$protected eq {{NULL}} || [[$protected getMaster] getName] ne {{sky130_fd_sc_hs__dfrtp_1}}}} {{error "first-stage identity differs"}}
set_dont_touch [get_cells {{{name}}}]
'''
    for corner in ('tt','ff','ss','sf','fs'):
        text+=f'read_spef -corner {corner} {{{path}}}\n'
    text+='repair_design -max_utilization 90 -verbose\n'
    for name in cells:
        text+=f'if {{[[[$block findInst {{{name}}}] getMaster] getName] ne {{sky130_fd_sc_hs__dfrtp_1}}}} {{error "first-stage master changed"}}\n'
    return text
