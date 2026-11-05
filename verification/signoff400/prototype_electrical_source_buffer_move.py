"""Move the measured long-branch buffer beside its weak XNOR source."""

def actions_for_plan(plan):
    if plan.get('branches') or len(plan['targets'])!=1:raise ValueError('one measured physical buffer move required')
    t=plan['targets'][0]
    if (t['action'],t['capture_master'],t['replacement_master'],t['driver_master'])!=('relocate','sky130_fd_sc_hs__clkbuf_2','sky130_fd_sc_hs__clkbuf_4','sky130_fd_sc_hs__xnor2_1'):raise ValueError('explicit characterized source-branch repair required')
    for name in (t['capture_cell'],t['driver_cell']):
        if any(c in name for c in '{}\\\n\r'):raise ValueError('invalid physical instance')
    return f'''set buffer [$block findInst {{{t['capture_cell']}}}]
set driver [$block findInst {{{t['driver_cell']}}}]
if {{$buffer eq {{NULL}} || $driver eq {{NULL}}}} {{error "measured source branch absent"}}
if {{[[$buffer getMaster] getName] ne {{{t['capture_master']}}} || [[$driver getMaster] getName] ne {{{t['driver_master']}}}}} {{error "source branch master changed"}}
if {{[[$buffer findITerm A] getNet] ne [[$driver findITerm Y] getNet]}} {{error "buffer no longer directly follows weak source"}}
foreach pin {{A X}} {{
 set wire [[[$buffer findITerm $pin] getNet] getWire]
 if {{$wire ne {{NULL}}}} {{odb::dbWire_destroy $wire}}
}}
replace_cell {{{t['capture_cell']}}} {t['replacement_master']}
lassign [$driver getLocation] x y
$buffer setOrient [$driver getOrient]
$buffer setLocation [expr {{$x+[[$driver getMaster] getWidth]}}] $y
$buffer setPlacementStatus PLACED
'''
