# Endpoint-local hold/removal repair. Never buffer a synchronizer stage link.
# Try at most four stages when one cell cannot cover the supplied corners.
# Partial chains must preserve global timing; final acceptance needs routed RC.
proc closure_repair_min {} {
    global closure_corners closure_protected_receivers
    set block [ord::get_db_block]
    set endpoints {}
    foreach corner $closure_corners {
        foreach path [find_timing_paths -corner $corner -path_delay min -group_path_count 40 -slack_max 0.08 -sort_by_slack] {
            set points [get_property $path points]
            set pin [get_full_name [get_property [lindex $points end] pin]]
            if {[file tail $pin] ni {D RESET_B}} {continue}
            if {$pin in $closure_protected_receivers} {
                closure_log [list protected_receiver_min $pin slack [get_property $path slack]]
                continue
            }
            dict set endpoints $pin 1
        }
    }
    set changes 0
    foreach pin [dict keys $endpoints] {
        set inst [$block findInst [file dirname $pin]]
        set sink [$inst findITerm [file tail $pin]]
        set source [$sink getNet]
        set index 0
        while {[$block findInst closure_min_$index] ne {NULL}} {incr index}
        set name closure_min_$index
        set global_max_before [closure_slack max]
        set global_min_before [closure_slack min]
        set buffers {}
        set best {}
        set best_setup -1e6
        for {set depth 1} {$depth <= 4} {incr depth} {
            set name closure_min_$index
            incr index
            while {[$block findInst closure_min_$index] ne {NULL}} {incr index}
            set buffer [closure_buffer $name sky130_fd_sc_hs__buf_4 [$sink getNet] [list $sink]]
            lappend buffers $buffer
            set output "$name/X"
            set partial {}
            set partial_min -1e6
            foreach suffix {buf_1 buf_2 buf_4 buf_8 buf_16 dlygate4sd1_1 dlygate4sd2_1 dlygate4sd3_1} {
                set master sky130_fd_sc_hs__$suffix
                if {[[ord::get_db] findMaster $master] eq {NULL}} {continue}
                replace_cell [get_cells [list $name]] $master
                set minimum [closure_slack min $output]
                set maximum [closure_slack max $output]
                if {$minimum >= 1e5 || $maximum >= 1e5} {continue}
                set global_min [closure_slack min]
                set global_max [closure_slack max]
                closure_log [list min_trial $pin depth $depth master $master hold $minimum setup $maximum global_hold $global_min global_setup $global_max]
                if {$maximum < 0.10 || $global_min < $global_min_before - 0.000001 || $global_max < min(0.10, $global_max_before) - 0.000001} {continue}
                if {$minimum >= 0.12 && $maximum > $best_setup} {
                    set best $master
                    set best_setup $maximum
                }
                if {$minimum > $partial_min} {set partial $master; set partial_min $minimum}
            }
            if {$best ne {}} {replace_cell [get_cells [list $name]] $best; break}
            if {$partial eq {}} {break}
            replace_cell [get_cells [list $name]] $partial
        }
        if {$best eq {}} {
            set protected [$inst isDoNotTouch]
            if {$protected} {unset_dont_touch [get_cells [list [$inst getName]]]}
            $sink disconnect
            $sink connect $source
            if {$protected} {set_dont_touch [get_cells [list [$inst getName]]]}
            foreach buffer [lreverse $buffers] {
                set net [[$buffer findITerm X] getNet]
                odb::dbInst_destroy $buffer
                odb::dbNet_destroy $net
            }
            closure_log [list min_unrepaired $pin reason no_setup_safe_chain]
        } else {
            closure_log [list min_repair_chain $pin stages [llength $buffers] setup $best_setup hold [closure_slack min $output]]
            incr changes
        }
    }
    return $changes
}
