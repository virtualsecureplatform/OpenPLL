"""Delay only the shared measured BBPD receive reset branch; no reset exceptions."""


def actions_for_plan(targets):
    if len(targets) != 1:
        raise ValueError('one measured shared reset branch required')
    target = targets[0]
    names = target['capture_cells']
    if (len(names) != 4 or len(set(names)) != 4 or target['buffers'] != 3
            or target['capture_master'] != 'sky130_fd_sc_hs__dfrtp_1'
            or any(any(c in n for c in '{}\\\n\r') for n in names)):
        raise ValueError('exact four-receiver three-buffer reset ECO required')
    text = 'set reset_sinks {}\nset original_reset {}\n'
    for name in names:
        text += f'''set sink [$block findInst {{{name}}}]
if {{$sink eq {{NULL}} || [[$sink getMaster] getName] ne {{sky130_fd_sc_hs__dfrtp_1}}}} {{error "reset receiver identity changed"}}
set term [$sink findITerm RESET_B]
set net [$term getNet]
if {{$net eq {{NULL}}}} {{error "receive reset disconnected"}}
if {{$original_reset eq {{}}}} {{set original_reset $net}}
if {{$original_reset ne $net}} {{error "receive resets no longer share one net"}}
lappend reset_sinks $term
'''
    text += '''lassign [$sink getLocation] sx sy
set orient [$sink getOrient]
set upstream $original_reset
'''
    for index in range(3):
        prefix = f'prototype_event_reset_branch_{index}'
        text += f'''set buffer [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__clkbuf_2] {prefix}]
$buffer setOrient $orient
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
    return text+'foreach term $reset_sinks {$term connect $upstream}\n'
