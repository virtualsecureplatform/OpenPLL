# Use stronger functionally identical allowed masters for extracted failures.
# Resolve all targets first so cell replacement cannot alter target discovery.
set block [ord::get_db_block]
set strongest [dict create @STRONGEST@]
set drivers [dict create]
foreach pair {@TARGETS@} {
    lassign $pair inst_name pin
    set inst [$block findInst $inst_name]
    if {$inst eq {NULL}} {error "missing electrical target instance"}
    set term [$inst findITerm $pin]
    if {$term eq {NULL}} {error "missing electrical target pin"}
    set net [$term getNet]
    if {$net eq {NULL}} {error "unconnected electrical target"}
    set outputs {}
    foreach candidate [$net getITerms] {
        if {[$candidate getIoType] eq {OUTPUT}} {lappend outputs $candidate}
    }
    if {[llength $outputs] != 1} {error "electrical target does not have one driver"}
    set driver [[lindex $outputs 0] getInst]
    dict set drivers [$driver getName] $driver
}
set resized 0
set saturated 0
foreach name [lsort [dict keys $drivers]] {
    set inst [dict get $drivers $name]
    set old [[$inst getMaster] getName]
    if {![regexp {^(sky130_fd_sc_hs__[a-z0-9]+)_([0-9]+)$} $old -> family strength]} {
        error "unsupported electrical driver family"
    }
    if {![dict exists $strongest $family]} {error "driver family outside allowed set"}
    set new [dict get $strongest $family]
    if {$old ne $new} {
        replace_cell $name $new
        incr resized
        puts "UPSIZED_ELECTRICAL_DRIVER name=$name old=$old new=$new"
    } else {
        incr saturated
        puts "SATURATED_ELECTRICAL_DRIVER name=$name master=$old"
    }
}
puts "UPSIZED_ELECTRICAL_TOTAL resized=$resized already_strongest=$saturated"
