# Restore inherited hold-buffered synchronizer links. A local launch-clock
# branch supplies hold margin; the first-Q to second-D connection stays direct.
proc closure_restore_receivers {} {
    global closure_receiver_pairs closure_buffer_masters
    set block [ord::get_db_block]
    set changed 0
    foreach inst [$block getInsts] {
        if {![string match {closure_cdc_clock_*} [$inst getName]]} {continue}
        set net [[$inst findITerm X] getNet]
        if {[$net getSigType] ne {CLOCK}} {
            $net setSigType CLOCK
            closure_log [list clock_net_role [$net getName] CLOCK]
            incr changed
        }
    }
    foreach pair $closure_receiver_pairs {
        lassign $pair source_name receiver_name
        set source [$block findInst $source_name]
        set receiver [$block findInst $receiver_name]
        if {$source eq {NULL} || $receiver eq {NULL}} {error "missing receiver pair $pair"}
        set data [$receiver findITerm D]
        set direct [[$source findITerm Q] getNet]
        set old [$data getNet]
        if {$old eq $direct} {continue}
        set before_min [closure_slack min]
        set before_max [closure_slack max]
        closure_reconnect $data $direct
        set clock [$source findITerm CLK]
        set clock_net [$clock getNet]
        set index 0
        while {[$block findInst closure_cdc_clock_$index] ne {NULL}} {incr index}
        set branch [closure_buffer closure_cdc_clock_$index sky130_fd_sc_hs__buf_2 $clock_net [list $clock]]
        [[$branch findITerm X] getNet] setSigType CLOCK
        set accepted 0
        foreach master {sky130_fd_sc_hs__buf_2 sky130_fd_sc_hs__buf_1 sky130_fd_sc_hs__buf_4 sky130_fd_sc_hs__dlygate4sd1_1 sky130_fd_sc_hs__dlygate4sd2_1 sky130_fd_sc_hs__dlygate4sd3_1} {
            if {$master ni $closure_buffer_masters} {continue}
            replace_cell [get_cells [list [$branch getName]]] $master
            set pin ${receiver_name}/D
            set minimum [closure_slack min $pin]
            set maximum [closure_slack max $pin]
            if {$minimum >= 0.12 && $maximum >= 0.10 &&
                [closure_slack min] >= min(0.05, $before_min) - 0.000001 &&
                [closure_slack max] >= $before_max - 0.000001} {
                set accepted 1
                closure_log [list direct_receiver $source_name $receiver_name clock_branch [$branch getName] master $master hold $minimum setup $maximum]
                break
            }
        }
        if {!$accepted} {
            error "no corner-safe direct receiver clock branch for $pair"
        }
        # Destroy only unused buffer chains, retaining shared branches and FFs.
        while {$old ne {NULL} && $old ne $direct && ![llength [closure_inputs $old]] && ![llength [$old getBTerms]]} {
            set driver {}
            foreach term [$old getITerms] {
                if {[$term getIoType] eq {OUTPUT}} {set driver [$term getInst]}
            }
            if {$driver eq {} || [[$driver getMaster] getName] ni $closure_buffer_masters || [closure_protected $driver]} {break}
            set parent [[$driver findITerm A] getNet]
            unset_dont_touch [get_cells [list [$driver getName]]]
            closure_log [list remove_receiver_delay [$driver getName]]
            odb::dbInst_destroy $driver
            odb::dbNet_destroy $old
            set old $parent
        }
        set_dont_touch [get_cells [list [$branch getName]]]
        incr changed
    }
    return $changed
}
