# Give critical launch FFs a local leaf from the same parent clock net.
# Keep the original root and leaf for other sinks. Trials preserve clock depth
# and screen incoming setup, outgoing hold and recovery across every corner.
proc closure_isolate_launch_clocks {} {
    global closure_launch_cells closure_buffer_masters
    set block [ord::get_db_block]
    set changes 0
    set index 0
    foreach name $closure_launch_cells {
        set inst [$block findInst $name]
        if {$inst eq {NULL} || [closure_protected $inst]} {continue}
        set clk [$inst findITerm CLK]
        if {$clk eq {NULL} || [$clk getNet] eq {NULL}} {continue}
        set old [$clk getNet]
        set leaf {NULL}
        set loads 0
        foreach term [$old getITerms] {
            if {[$term getIoType] eq {OUTPUT}} {set leaf [$term getInst]}
            if {[$term getIoType] eq {INPUT}} {incr loads}
        }
        if {$leaf eq {NULL} || $loads < 16 || [[$leaf getMaster] getName] ni $closure_buffer_masters} {continue}
        set input [$leaf findITerm A]
        if {$input eq {NULL} || [$input getNet] eq {NULL}} {continue}
        set parent [$input getNet]
        # A port-driven buffer is a root; do not bypass its stage.
        if {[llength [$parent getBTerms]] != 0} {continue}
        set before [closure_cell_slack max $inst]
        if {$before >= 0.10} {continue}
        set max_before [closure_slack max]
        set min_before [closure_slack min]
        set floor [expr {min(0.05, $min_before) - 0.000001}]
        while {[$block findInst closure_launch_clock_$index] ne {NULL}} {incr index}
        set branch_name closure_launch_clock_$index
        set protected [$inst isDoNotTouch]
        if {$protected} {unset_dont_touch [get_cells [list $name]]}
        set best {}
        set best_slack $before
        foreach master {sky130_fd_sc_hs__buf_16 sky130_fd_sc_hs__clkbuf_16} {
            set buffer [odb::dbInst_create $block [[ord::get_db] findMaster $master] $branch_name]
            set net [odb::dbNet_create $block ${branch_name}_out]
            $net setSigType CLOCK
            [$buffer findITerm A] connect $parent
            [$buffer findITerm X] connect $net
            $clk disconnect
            $clk connect $net
            $buffer setLocation {*}[$inst getLocation]
            $buffer setPlacementStatus PLACED
            set maximum [closure_cell_slack max $inst]
            set minimum [closure_cell_slack min $inst]
            if {$minimum >= 0.08 && [closure_slack min] >= $floor &&
                [closure_slack max] >= $max_before - 0.000001 && $maximum > $best_slack + 0.01} {
                set best $master
                set best_slack $maximum
            }
            $clk disconnect
            $clk connect $old
            odb::dbInst_destroy $buffer
            odb::dbNet_destroy $net
        }
        if {$best eq {}} {
            if {$protected} {set_dont_touch [get_cells [list $name]]}
            continue
        }
        set buffer [odb::dbInst_create $block [[ord::get_db] findMaster $best] $branch_name]
        set net [odb::dbNet_create $block ${branch_name}_out]
        $net setSigType CLOCK
        [$buffer findITerm A] connect $parent
        [$buffer findITerm X] connect $net
        $clk disconnect
        $clk connect $net
        $buffer setLocation {*}[$inst getLocation]
        $buffer setPlacementStatus PLACED
        set_dont_touch [get_cells [list $branch_name]]
        closure_log [list launch_clock_leaf $name $branch_name $best old_leaf [$leaf getName] parent [$parent getName] setup_before $before setup_after $best_slack hold_after [closure_slack min]]
        if {$protected} {set_dont_touch [get_cells [list $name]]}
        incr changes
        incr index
    }
    return $changes
}
