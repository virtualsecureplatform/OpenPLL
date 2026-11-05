# Delay only raw BBPD guard-data branches. Keep pulse clocks and their CTS
# sinks untouched, and continue timing both cross-pulse paths.
set block [ord::get_db_block]
set guard_index 0
foreach port [$block getBTerms] {
    if {[string range [$port getName] 0 4] ne {BBPD[}} {continue}
    set queue [list [$port getNet]]
    set visited {}
    while {[llength $queue]} {
        set net [lindex $queue 0]
        set queue [lrange $queue 1 end]
        if {[$net getName] in $visited} {continue}
        lappend visited [$net getName]
        set guards {}
        foreach term [$net getITerms] {
            if {[$term getIoType] ne {INPUT} || [$term getSigType] ni {SIGNAL CLOCK}} {continue}
            set inst [$term getInst]
            if {[string match {*__clkbuf_*} [[$inst getMaster] getName]]} {
                lappend queue [[$inst findITerm X] getNet]
            } elseif {[string match {pulse_guard_*} [$inst getName]]} {
                continue  ;# Already guarded; repeated repair must be idempotent.
            } elseif {[[$term getMTerm] getName] ne {CLK}} {
                lappend guards $term
            }
        }
        if {![llength $guards]} {continue}
        while {[$block findInst pulse_guard_$guard_index] ne {NULL}} {incr guard_index}
        set name pulse_guard_$guard_index
        incr guard_index
        set delay [odb::dbInst_create $block [[ord::get_db] findMaster @SCL@__dlygate4sd3_1] $name]
        set output [odb::dbNet_create $block ${name}_out]
        [$delay findITerm A] connect $net
        [$delay findITerm X] connect $output
        $delay setLocation {*}[[[lindex $guards 0] getInst] getLocation]
        $delay setPlacementStatus PLACED
        foreach term $guards {$term disconnect; $term connect $output}
        set_dont_touch [get_cells $name]
        puts "PULSE_GUARD_DATA_DELAY port=[$port getName] sinks=[llength $guards]"
    }
}
