# Copy overloaded data drivers while preserving sequential latency. Synchronizer
# FFs and reset-release FFs are never replicated. New FFs share the exact clock,
# data and logical reset of their source. Full extracted timing/proof is required.
proc closure_reconnect {sink net} {
    set owner [$sink getInst]
    set protected [$owner isDoNotTouch]
    if {$protected} {unset_dont_touch [get_cells [list [$owner getName]]]}
    $sink disconnect
    $sink connect $net
    if {$protected} {set_dont_touch [get_cells [list [$owner getName]]]} 
}
proc closure_clone_drivers {} {
    global closure_corners closure_async_cells
    set block [ord::get_db_block]
    set candidates {}
    foreach corner $closure_corners {
        foreach path [find_timing_paths -corner $corner -path_delay max -path_group PLLOUT -group_path_count 20 -slack_max 0.20 -sort_by_slack] {
            foreach point [get_property $path points] {
                set pin [get_full_name [get_property $point pin]]
                set inst [$block findInst [file dirname $pin]]
                if {$inst eq {NULL} || [closure_protected $inst]} {continue}
                set output [closure_output $inst]
                if {$pin ne $output || [$inst getName] in $closure_async_cells} {continue}
                set master [[$inst getMaster] getName]
                if {[$inst findITerm Q] ne {NULL}} {
                    if {![regexp {__(dfrtp|dfstp)_[0-9]+$} $master]} {continue}
                } elseif {[$inst findITerm CLK] ne {NULL} || [regexp {__(conb|dl|probe|lpflow)} $master]} {
                    continue
                }
                dict set candidates [$inst getName] 1
            }
        }
    }
    set changed 0
    foreach name [dict keys $candidates] {
        set source [$block findInst $name]
        if {$source eq {NULL}} {continue}
        set output [closure_output $source]
        if {[closure_slack max $output] >= 0.20} {continue}
        set terminal [$source findITerm [file tail $output]]
        set net [$terminal getNet]
        if {[llength [$net getBTerms]]} {continue}
        set sinks [closure_inputs $net]
        # Flatten only ordinary fanout buffers. Keep hold cells and pulse guards.
        # Retain the unused buffer physically so rollback preserves SPEF names.
        set placeholders {}
        set expanded {}
        foreach sink $sinks {
            set owner [$sink getInst]
            set owner_name [$owner getName]
            if {[string match {*__buf_*} [[$owner getMaster] getName]] && ![closure_protected $owner] &&
                ([string match {split*} $owner_name] || [string match {clone*} $owner_name] || [string match {fanout*} $owner_name]) &&
                ![llength [[[$owner findITerm X] getNet] getBTerms]]} {
                set children [closure_inputs [[$owner findITerm X] getNet]]
                if {[llength $children] > 1} {
                    lappend placeholders $sink
                    set expanded [concat $expanded $children]
                    continue
                }
            }
            lappend expanded $sink
        }
        set sinks $expanded
        set is_ff [expr {[$source findITerm Q] ne {NULL}}]
        if {[llength $sinks] < 2} {continue}
        set bank_limit [expr {$is_ff && [llength $sinks] > 3 ? 3 : 1}]
        set banks [closure_banks $sinks $bank_limit 0.05]
        if {[llength $banks] < 2} {continue}
        set before_local [closure_slack max $output]
        set before_max [closure_slack max]
        set before_min [closure_slack min]
        set saved {}
        foreach sink $sinks {lappend saved [list $sink [$sink getNet]]}
        set copies {}
        set nets {}
        set bi 0
        foreach bank $banks {
            if {$bi == 0} {
                foreach sink $bank {closure_reconnect $sink $net}
            } else {
                set index 0
                while {[$block findInst closure_clone_$index] ne {NULL}} {incr index}
                set copy [odb::dbInst_create $block [$source getMaster] closure_clone_$index]
                set x 0
                set y 0
                foreach sink $bank {
                    lassign [[$sink getInst] getLocation] sx sy
                    incr x $sx
                    incr y $sy
                }
                $copy setLocation [expr {$x / [llength $bank]}] [expr {$y / [llength $bank]}]
                $copy setPlacementStatus PLACED
                foreach input [$source getITerms] {
                    if {[$input getIoType] eq {INPUT} && [$input getSigType] in {SIGNAL CLOCK}} {
                        [$copy findITerm [[$input getMTerm] getName]] connect [$input getNet]
                    }
                }
                set copy_net [odb::dbNet_create $block closure_clone_${index}_out]
                [$copy findITerm [file tail $output]] connect $copy_net
                foreach sink $bank {closure_reconnect $sink $copy_net}
                lappend copies $copy
                lappend nets $copy_net
            }
            incr bi
        }
        set reset_leaves {}
        if {[$source findITerm Q] ne {NULL}} {
            foreach pin {RESET_B SET_B} {
                set groups {}
                foreach copy $copies {
                    set reset [$copy findITerm $pin]
                    if {$reset ne {NULL}} {
                        set reset_net [$reset getNet]
                        dict lappend groups [$reset_net getName] $reset
                    }
                }
                dict for {reset_name reset_sinks} $groups {
                    set reset_net [$block findNet $reset_name]
                    set driver {}
                    foreach term [$reset_net getITerms] {
                        if {[$term getIoType] eq {OUTPUT}} {set driver [$term getInst]}
                    }
                    if {$driver ne {} && [string match {closure_reset_*_leaf_*} [$driver getName]]} {
                        set index 0
                        while {[$block findInst closure_clone_reset_$index] ne {NULL}} {incr index}
                        set leaf [closure_buffer closure_clone_reset_$index sky130_fd_sc_hs__buf_16 [[$driver findITerm A] getNet] $reset_sinks]
                        lappend reset_leaves [list $leaf $reset_net $reset_sinks]
                    }
                }
            }
        }
        set minimum [closure_slack min]
        set maximum [closure_slack max]
        set local 1e6
        set timed 1
        foreach inst [concat [list $source] $copies] {
            set score [closure_slack max [closure_output $inst]]
            if {$score > 1e5} {set timed 0}
            set local [expr {min($local, $score)}]
        }
        # Global setup must improve or remain stable, and all holds remain safe.
        if {$minimum < min(0.05, $before_min) - 0.000001 || $maximum < $before_max - 0.000001 || $local < $before_local + 0.01 || !$timed} {
            foreach row $reset_leaves {
                lassign $row leaf reset_net reset_sinks
                set extra [[$leaf findITerm X] getNet]
                foreach reset $reset_sinks {closure_reconnect $reset $reset_net}
                odb::dbInst_destroy $leaf
                odb::dbNet_destroy $extra
            }
            foreach row $saved {closure_reconnect [lindex $row 0] [lindex $row 1]}
            foreach copy $copies {odb::dbInst_destroy $copy}
            foreach extra $nets {odb::dbNet_destroy $extra}
            closure_log [list clone_rejected $name setup_before $before_max setup_after $maximum hold_after $minimum]
        } else {
            closure_log [list clone_driver $name banks [llength $banks] sinks [llength $sinks] bypassed [llength $placeholders] setup_before $before_max setup_after $maximum local_setup $local hold_after $minimum]
            foreach input $placeholders {
                set unused [$input getInst]
                set old_net [[$unused findITerm X] getNet]
                if {![llength [closure_inputs $old_net]] && ![llength [$old_net getBTerms]]} {
                    unset_dont_touch [get_cells [list [$unused getName]]]
                    closure_log [list remove_unused_fanout_buffer [$unused getName]]
                    odb::dbInst_destroy $unused
                    odb::dbNet_destroy $old_net
                }
            }
            incr changed
        }
    }
    return $changed
}
