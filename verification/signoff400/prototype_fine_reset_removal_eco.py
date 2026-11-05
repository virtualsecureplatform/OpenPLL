"""Delay only measured reset leaf branches; preserve ordinary data connections."""

def actions_for_plan(plan):
    if plan['targets'] or plan['branches'] or len(plan['reset_branches'])!=5:raise ValueError('five measured reset branches required')
    text=''
    for index,b in enumerate(plan['reset_branches']):
        if b['capture_pin']!='SET_B' or b['capture_master']!='sky130_fd_sc_hs__dfstp_1' or b['buffers']!=8 or b['last_buffer_master']!='sky130_fd_sc_hs__clkbuf_4':raise ValueError('explicit characterized reset delay required')
        text+='set sinks {}\nset original_reset {}\nset sx 0\nset sy 0\n'
        if not b['capture_cells'] or len(set(b['capture_cells']))!=len(b['capture_cells']):raise ValueError('unique reset receivers required')
        for name in b['capture_cells']:
            if any(c in name for c in '{}\\\n\r'):raise ValueError('invalid receiver name')
            text+=f'''set sink [$block findInst {{{name}}}]
if {{$sink eq {{NULL}} || [[$sink getMaster] getName] ne {{sky130_fd_sc_hs__dfstp_1}}}} {{error "reset receiver changed"}}
set term [$sink findITerm SET_B]
set net [$term getNet]
if {{$net eq {{NULL}}}} {{error "reset receiver disconnected"}}
if {{$original_reset eq {{}}}} {{set original_reset $net}}
if {{$original_reset ne $net}} {{error "reset branch no longer shares one leaf net"}}
lappend sinks $term
lassign [$sink getLocation] x y
incr sx $x
incr sy $y
'''
        text+='set sx [expr {$sx/[llength $sinks]}]\nset sy [expr {$sy/[llength $sinks]}]\nset upstream $original_reset\n'
        for stage in range(8):
            master='sky130_fd_sc_hs__clkbuf_4' if stage==7 else 'sky130_fd_sc_hs__clkbuf_2';prefix=f'prototype_fine_reset_delay_{index}_{stage}'
            text+=f'''if {{[$block findInst {prefix}] ne {{NULL}} || [$block findNet {prefix}_net] ne {{NULL}}}} {{error "fresh reset-delay names required"}}
set buffer [odb::dbInst_create $block [[ord::get_db] findMaster {master}] {prefix}]
$buffer setOrient [$sink getOrient]
$buffer setLocation $sx $sy
$buffer setPlacementStatus PLACED
set local [odb::dbNet_create $block {prefix}_net]
[$buffer findITerm A] connect $upstream
[$buffer findITerm X] connect $local
foreach pin {{VPWR VPB}} {{[$buffer findITerm $pin] connect [$block findNet VDD]}}
foreach pin {{VGND VNB}} {{[$buffer findITerm $pin] connect [$block findNet VSS]}}
if {{[$upstream getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$upstream getWire]}}
set upstream $local
'''
        text+='foreach term $sinks {$term connect $upstream}\n'
    return text
