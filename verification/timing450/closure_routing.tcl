# Record topology and pin geometry before an ECO. Existing ROUTED wires are
# mutable input to the pinned detailed router; invalid endpoint geometry must
# be discarded before reuse. Supply special wires are kept separately by ODB.
proc closure_connect_power {} {
    set protected {}
    foreach inst [[ord::get_db_block] getInsts] {
        if {![$inst isDoNotTouch]} {continue}
        foreach term [$inst getITerms] {
            if {[$term getSigType] in {POWER GROUND} && [$term getNet] eq {NULL}} {
                lappend protected [$inst getName]
                unset_dont_touch [get_cells [list [$inst getName]]]
                break
            }
        }
    }
    set code [catch {global_connect} result options]
    foreach name $protected {set_dont_touch [get_cells [list $name]]}
    if {$code} {return -options $options $result}
    set missing {}
    foreach inst [[ord::get_db_block] getInsts] {
        foreach term [$inst getITerms] {
            if {[$term getSigType] in {POWER GROUND} && [$term getNet] eq {NULL}} {
                lappend missing "[$inst getName]/[[$term getMTerm] getName]"
            }
        }
    }
    puts "CLOSURE power_connect restored_protection=[llength $protected] missing=[llength $missing]"
    if {[llength $missing]} {error "Unconnected ECO supplies: $missing"}
}
# Protected ECO clock leaves can bypass row-orientation correction in DPL.
# Align their supply rails before invalidating and rebuilding signal routes.
proc closure_align_clock_rows {} {
    set block [ord::get_db_block]
    set rows {}
    foreach row [$block getRows] {
        lassign [$row getOrigin] x y
        dict set rows $y [$row getOrient]
    }
    set changed 0
    foreach inst [$block getInsts] {
        if {![string match closure_launch_clock_* [$inst getName]]} {continue}
        lassign [$inst getLocation] x y
        if {![dict exists $rows $y]} {error "ECO clock leaf is off row: [$inst getName]"}
        set orient [dict get $rows $y]
        if {[$inst getOrient] eq $orient} {continue}
        set protected [$inst isDoNotTouch]
        if {$protected} {unset_dont_touch [get_cells [list [$inst getName]]]}
        $inst setOrient $orient
        $inst setLocation $x $y
        if {$protected} {set_dont_touch [get_cells [list [$inst getName]]]}
        incr changed
    }
    puts "CLOSURE clock_row_orientation corrected=$changed"
    return $changed
}
proc closure_place_signatures {} {
    set signatures {}
    foreach inst [[ord::get_db_block] getInsts] {
        dict set signatures [$inst getName] [list [[$inst getMaster] getName] \
            [$inst getLocation] [$inst getOrient]]
    }
    return $signatures
}
proc closure_legalize_preserving {before} {
    # Unchanged cells already have legal placement. Temporarily fix them so
    # legalization does not disturb their routing and clock geometry.
    set block [ord::get_db_block]
    set frozen {}
    set released {}
    foreach inst [$block getInsts] {
        set name [$inst getName]
        set signature [list [[$inst getMaster] getName] [$inst getLocation] [$inst getOrient]]
        if {[dict exists $before $name] && $signature eq [dict get $before $name] &&
            [$inst getPlacementStatus] eq {PLACED}} {
            dict set frozen $name [$inst getPlacementStatus]
            $inst setPlacementStatus FIRM
        } elseif {[$inst isDoNotTouch] && [$inst getPlacementStatus] eq {PLACED}} {
            # Newly protected ECO cells still need their first legalization.
            lappend released $name
            unset_dont_touch [get_cells [list $name]]
        }
    }
    set code [catch {detailed_placement} result options]
    foreach name $released {set_dont_touch [get_cells [list $name]]}
    set moved {}
    foreach name [dict keys $frozen] {
        set inst [$block findInst $name]
        $inst setPlacementStatus [dict get $frozen $name]
        if {[list [[$inst getMaster] getName] [$inst getLocation] [$inst getOrient]] ne [dict get $before $name]} {
            lappend moved $name
        }
    }
    puts "CLOSURE preserved_placement unchanged=[dict size $frozen]"
    if {[llength $moved]} {error "Unchanged placement moved: $moved"}
    if {$code} {return -options $options $result}
    check_placement -verbose
}
proc closure_wire_signatures {} {
    set signatures {}
    foreach net [[ord::get_db_block] getNets] {
        if {[$net getSigType] in {POWER GROUND}} {continue}
        set terms {}
        foreach term [$net getITerms] {
            set inst [$term getInst]
            lappend terms [list [$inst getName] [[$term getMTerm] getName] \
                [[$inst getMaster] getName] [$inst getLocation] [$inst getOrient]]
        }
        foreach term [$net getBTerms] {lappend terms [list PORT [$term getName]]}
        dict set signatures [$net getName] [list [$net getSigType] [lsort $terms]]
    }
    return $signatures
}
proc closure_clear_changed_wires {before} {
    set after [closure_wire_signatures]
    set cleared {}
    set retained 0
    foreach net [[ord::get_db_block] getNets] {
        if {[$net getSigType] in {POWER GROUND} || [$net getWire] eq {NULL}} {continue}
        set name [$net getName]
        if {![dict exists $before $name] || [dict get $before $name] ne [dict get $after $name]} {
            odb::dbWire_destroy [$net getWire]
            lappend cleared $name
        } else {
            incr retained
        }
    }
    puts "CLOSURE routing_input retained=$retained cleared=[llength $cleared]"
    return $cleared
}
