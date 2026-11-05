"""Render checked equivalent-size changes and spatially grouped branch buffers."""
from prototype_measured_path_eco import buffer_actions

def actions_for_plan(plan):
    text=''
    for t in plan['targets']:
        n=t['capture_cell'];old=t['capture_master'];new=t['replacement_master']
        if any(c in n for c in '{}\\\n\r') or old.rsplit('_',1)[0]!=new.rsplit('_',1)[0]:raise ValueError('invalid same-family resize')
        text+=f'''set inst [$block findInst {{{n}}}]
if {{$inst eq {{NULL}} || [[$inst getMaster] getName] ne {{{old}}}}} {{error "sizing source changed"}}
replace_cell {{{n}}} {new}
'''
    for index,branch in enumerate(plan['branches']):
        if branch['max_sinks_per_buffer']!=8 or branch['buffer_master']!='sky130_fd_sc_hs__clkbuf_2':raise ValueError('bounded characterized branch required')
        d=branch['driver'];text+=f'''set driver [$block findInst {{{d['cell']}}}]
if {{$driver eq {{NULL}} || [[$driver getMaster] getName] ne {{{d['master']}}}}} {{error "branch driver changed"}}
set upstream [[$driver findITerm {d['pin']}] getNet]
if {{$upstream eq {{NULL}}}} {{error "branch disconnected"}}
set sinks {{}}
'''
        for s in branch['sinks']:
            if any(c in s['cell'] for c in '{}\\\n\r'):raise ValueError('invalid sink')
            text+=f'''set sink [$block findInst {{{s['cell']}}}]
if {{$sink eq {{NULL}} || [[$sink getMaster] getName] ne {{{s['master']}}}}} {{error "branch receiver changed"}}
set term [$sink findITerm {s['pin']}]
if {{[$term getNet] ne $upstream}} {{error "branch no longer shares source net"}}
lassign [$sink getLocation] x y
lappend sinks [list $x $y $sink $term]
'''
        text+='''set sinks [lsort -integer -index 0 $sinks]
set count [llength $sinks]
'''
        text+=f'''for {{set start 0}} {{$start < $count}} {{incr start 8}} {{
 set group [lrange $sinks $start [expr {{$start+7}}]]
 set sx 0; set sy 0
 foreach item $group {{incr sx [lindex $item 0]; incr sy [lindex $item 1]}}
 set first [lindex [lindex $group 0] 2]
 set prefix prototype_observed_load_followup_branch_{index}_$start
 if {{[$block findInst $prefix] ne {{NULL}} || [$block findNet ${{prefix}}_net] ne {{NULL}}}} {{error "fresh electrical branch names required"}}
 set buffer [odb::dbInst_create $block [[ord::get_db] findMaster sky130_fd_sc_hs__clkbuf_2] $prefix]
 $buffer setOrient [$first getOrient]
 $buffer setLocation [expr {{$sx/[llength $group]}}] [expr {{$sy/[llength $group]}}]
 $buffer setPlacementStatus PLACED
 set local [odb::dbNet_create $block ${{prefix}}_net]
 [$buffer findITerm A] connect $upstream
 [$buffer findITerm X] connect $local
 foreach pin {{VPWR VPB}} {{[$buffer findITerm $pin] connect [$block findNet VDD]}}
 foreach pin {{VGND VNB}} {{[$buffer findITerm $pin] connect [$block findNet VSS]}}
 foreach item $group {{[lindex $item 3] connect $local}}
}}
if {{[$upstream getWire] ne {{NULL}}}} {{odb::dbWire_destroy [$upstream getWire]}}
'''
    targets=plan.get('short_data_targets',[])
    if any(t.get('capture_pin')!='D' or t.get('buffers')!=1 or not t.get('capture_master','').startswith('sky130_fd_sc_hs__dfrtp_') for t in targets):raise ValueError('bounded measured FF D-pin repairs required')
    return text+(buffer_actions(targets).replace('prototype_path_closure_', 'prototype_observed_load_followup_hold_') if targets else '')
