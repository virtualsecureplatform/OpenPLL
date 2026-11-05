# Targeted ECOs. All timing decisions use the nine explicitly loaded corners.
# No optimizer is permitted to change clock trees or synchronizer connections.
proc closure_slack {kind {pin {}}} {
    global closure_corners
    set worst 1e6
    foreach corner $closure_corners {
        set args [list -corner $corner -path_delay $kind -group_path_count 1 -sort_by_slack]
        if {$pin ne {}} {lappend args -through [get_pins [list $pin]]}
        foreach path [find_timing_paths {*}$args] {
            set worst [expr {min($worst, [get_property $path slack])}]
        }
    }
    return $worst
}
proc closure_maximum_snapshot {} {
    # Record every failing endpoint, separately for each cell/RC corner.
    # A single global worst slack can hide a newly failing, previously good
    # endpoint while an unrelated recovery path remains the worst path.
    global closure_corners
    set snapshot {}
    foreach corner $closure_corners {
        foreach path [find_timing_paths -corner $corner -path_delay max \
                -group_path_count 100000 -endpoint_path_count 1 -slack_max 0.100001] {
            set point [lindex [get_property $path points] end]
            set key [list $corner [get_full_name [get_property $point pin]]]
            set value [get_property $path slack]
            if {![dict exists $snapshot $key] || $value < [dict get $snapshot $key]} {
                dict set snapshot $key $value
            }
        }
    }
    return $snapshot
}
proc closure_preserves_maximum_floors {before} {
    dict for {key value} [closure_maximum_snapshot] {
        set floor 0.10
        if {[dict exists $before $key]} {set floor [expr {min($floor, [dict get $before $key])}]}
        if {$value < $floor - 0.000001} {return 0}
    }
    return 1
}
proc closure_protect_clocks {} {
    global closure_clock_cells
    set closure_clock_cells {}
    set block [ord::get_db_block]
    set queue {}
    foreach inst [$block getInsts] {
        set pin [$inst findITerm CLK]
        if {$pin ne {NULL} && [$pin getNet] ne {NULL}} {lappend queue [$pin getNet]}
    }
    set seen {}
    while {[llength $queue]} {
        set net [lindex $queue 0]
        set queue [lrange $queue 1 end]
        if {[dict exists $seen [$net getName]]} {continue}
        dict set seen [$net getName] 1
        foreach driver [$net getITerms] {
            if {[$driver getIoType] ne {OUTPUT}} {continue}
            set owner [$driver getInst]
            dict set closure_clock_cells [$owner getName] 1
            set inputs {}
            foreach pin [$owner getITerms] {
                if {[$pin getIoType] eq {INPUT} && [$pin getSigType] in {SIGNAL CLOCK}} {lappend inputs $pin}
            }
            # Clock buffers/inverters have one input; a source FF terminates the walk.
            if {[llength $inputs] == 1 && [[lindex $inputs 0] getNet] ne {NULL}} {
                lappend queue [[lindex $inputs 0] getNet]
            }
        }
    }
    closure_log [list protected_clock_cells [dict size $closure_clock_cells]]
}
proc closure_protected {inst} {
    global closure_clock closure_clock_cells
    set name [$inst getName]
    set master [[$inst getMaster] getName]
    if {$name eq $closure_clock} {return 1}
    foreach pattern {clk* fine_clock_* fine_signal_* pulse_guard_* export_* constant_*} {
        if {[string match $pattern $name]} {return 1}
    }
    if {[dict exists $closure_clock_cells $name]} {return 1}
    # Protect any buffer whose output directly drives a clock pin.
    foreach term [$inst getITerms] {
        if {[$term getIoType] ne {OUTPUT} || [$term getNet] eq {NULL}} {continue}
        foreach sink [[$term getNet] getITerms] {
            if {[$sink getIoType] eq {INPUT} && [[$sink getMTerm] getName] eq {CLK}} {return 1}
        }
    }
    return 0
}
proc closure_output {inst} {
    foreach term [$inst getITerms] {
        if {[$term getIoType] eq {OUTPUT} && [$term getSigType] eq {SIGNAL}} {
            return "[$inst getName]/[[$term getMTerm] getName]"
        }
    }
    return {}
}
proc closure_log {message} {
    global closure_journal
    puts "CLOSURE $message"
    puts $closure_journal $message
    flush $closure_journal
}
proc closure_cell_slack {kind inst} {
    # Receive setup/recovery arcs matter as well as launched Q paths. A FF
    # replacement must improve its worst affected path, whichever side it is on.
    set sequential [regexp {__(dfrtp|dfstp|dfrbp|dfsbp)_[0-9]+$} [[$inst getMaster] getName]]
    set worst 1e6
    foreach term [$inst getITerms] {
        if {[$term getNet] eq {NULL}} {continue}
        set pin [[$term getMTerm] getName]
        if {([$term getIoType] eq {OUTPUT} && [$term getSigType] eq {SIGNAL}) ||
            ($sequential && $pin in {D RESET_B SET_B})} {
            set worst [expr {min($worst, [closure_slack $kind "[$inst getName]/$pin"])}]
        }
    }
    return $worst
}
proc closure_optimize {} {
    global closure_corners closure_buffer_masters
    set block [ord::get_db_block]
    set changes 0
    while {1} {
        set candidates {}
        foreach corner $closure_corners {
            foreach path [find_timing_paths -corner $corner -path_delay max -group_path_count 40 -slack_max 0.25 -sort_by_slack] {
                foreach point [get_property $path points] {
                    set pin [get_full_name [get_property $point pin]]
                    set name [file dirname $pin]
                    set inst [$block findInst $name]
                    if {$inst eq {NULL} || [closure_protected $inst]} {continue}
                    set master [[$inst getMaster] getName]
                    if {[regexp {__(buf|dlygate|inv|clkinv|[a-z]*[0-9][a-z0-9]*)[^_]*_[0-9]+$} $master] && ![regexp {__(df|sd|ed|lpflow|dl|conb)} $master]} {
                        # dlygate is combinational; sequential dl* is excluded below.
                        dict set candidates $name 1
                    } elseif {$master in $closure_buffer_masters || [regexp {__(dfrtp|dfstp|dfrbp|dfsbp)_[0-9]+$} $master]} {
                        # A compatible receive FF is allowed; its direct stage
                        # connection and clock/reset nets are kept intact.
                        dict set candidates $name 1
                    }
                }
            }
        }
        set pass_changes 0
        foreach name [dict keys $candidates] {
            set inst [$block findInst $name]
            set original [[$inst getMaster] getName]
            set output [closure_output $inst]
            if {$output eq {}} {continue}
            set before [closure_cell_slack max $inst]
            if {$before >= 0.25} {continue}
            set global_before [closure_slack max]
            set maximum_before [closure_maximum_snapshot]
            set min_before [closure_slack min]
            set floor [expr {min(0.05, $min_before) - 0.000001}]
            set choices {}
            if {[string match {*__dlygate*} $original] || [string match {*__bufbuf*} $original] || [regexp {__buf_[0-9]+$} $original]} {
                foreach suffix {buf_1 buf_2 buf_4 buf_8 buf_16 dlygate4sd1_1 dlygate4sd2_1} {
                    lappend choices sky130_fd_sc_hs__$suffix
                }
            } elseif {[regexp {^(.*__(?:dfrtp|dfstp|dfrbp|dfsbp))_([0-9]+)$} $original -> family strength]} {
                # Smaller FFs can have lower intrinsic delay at light loads.
                foreach next {1 2 4 8 16} {if {$next != $strength} {lappend choices ${family}_$next}}
            } elseif {[regexp {^(.*)_([0-9]+)$} $original -> family strength]} {
                foreach next {2 4 8 16} {if {$next > $strength} {lappend choices ${family}_$next}}
            }
            set best $original
            set best_slack $before
            set best_min $min_before
            foreach master $choices {
                if {[[ord::get_db] findMaster $master] eq {NULL}} {continue}
                unset_dont_touch [get_cells [list $name]]
                replace_cell [get_cells [list $name]] $master
                set slack [closure_cell_slack max $inst]
                # Failed local improvements cannot be accepted. Avoid full
                # design max/min searches for those trials.
                if {$slack > $best_slack + 0.002 && [closure_cell_slack min $inst] >= 0.05} {
                    set minimum [closure_slack min]
                    if {$minimum >= $floor && [closure_slack max] >= $global_before - 0.000001 &&
                            [closure_preserves_maximum_floors $maximum_before]} {
                        set best $master
                        set best_slack $slack
                        set best_min $minimum
                    }
                }
                replace_cell [get_cells [list $name]] $original
            }
            if {$best ne $original} {
                replace_cell [get_cells [list $name]] $best
                closure_log [list resize $name $original $best setup_before $before setup_after $best_slack hold_after $best_min]
                incr changes
                incr pass_changes
            }
        }
        if {$pass_changes == 0} {break}
    }
    closure_log [list sizing_complete changes $changes setup [closure_slack max] hold [closure_slack min]]
    return $changes
}
proc closure_inputs {net} {
    set result {}
    foreach term [$net getITerms] {
        if {[$term getIoType] eq {INPUT} && [$term getSigType] in {SIGNAL CLOCK}} {lappend result $term}
    }
    return $result
}
proc closure_buffer {name master source sinks} {
    set block [ord::get_db_block]
    if {[$block findInst $name] ne {NULL}} {error "duplicate ECO instance $name"}
    set inst [odb::dbInst_create $block [[ord::get_db] findMaster $master] $name]
    set net [odb::dbNet_create $block ${name}_out]
    [$inst findITerm A] connect $source
    [$inst findITerm X] connect $net
    set x 0
    set y 0
    foreach sink $sinks {
        lassign [[$sink getInst] getLocation] sx sy
        incr x $sx
        incr y $sy
        set owner [$sink getInst]
        set protected [$owner isDoNotTouch]
        if {$protected} {unset_dont_touch [get_cells [list [$owner getName]]]}
        $sink disconnect
        $sink connect $net
        if {$protected} {set_dont_touch [get_cells [list [$owner getName]]]}
    }
    $inst setLocation [expr {$x / [llength $sinks]}] [expr {$y / [llength $sinks]}]
    $inst setPlacementStatus PLACED
    return $inst
}
proc closure_cap {term} {
    global closure_pin_caps
    set key "[[[$term getInst] getMaster] getName]/[[$term getMTerm] getName]"
    if {![dict exists $closure_pin_caps $key]} {error "missing pin capacitance $key"}
    return [dict get $closure_pin_caps $key]
}
proc closure_sort_sinks {sinks} {
    set ordered {}
    foreach sink $sinks {
        lassign [[$sink getInst] getLocation] x y
        lappend ordered [list $x $y [[$sink getInst] getName] [[$sink getMTerm] getName] $sink]
    }
    set result {}
    foreach row [lsort -integer -index 0 [lsort -integer -index 1 $ordered]] {lappend result [lindex $row 4]}
    return $result
}
proc closure_banks {sinks count cap} {
    set banks {}
    set bank {}
    set load 0.0
    foreach sink [closure_sort_sinks $sinks] {
        set extra [closure_cap $sink]
        if {[llength $bank] && ([llength $bank] >= $count || $load + $extra > $cap)} {
            lappend banks $bank
            set bank {}
            set load 0.0
        }
        lappend bank $sink
        set load [expr {$load + $extra}]
    }
    if {[llength $bank]} {lappend banks $bank}
    return $banks
}
proc closure_reset_banks {} {
    global closure_reset_sources closure_buffer_masters
    set block [ord::get_db_block]
    set index 0
    set changes 0
    set sources $closure_reset_sources
    global closure_corners
    foreach corner $closure_corners {
        foreach path [find_timing_paths -corner $corner -path_delay max -path_group asynchronous -group_path_count 30 -slack_max 0.25] {
            set first [lindex [get_property $path points] 0]
            set pin [get_full_name [get_property $first pin]]
            if {[file tail $pin] eq {Q}} {lappend sources [file dirname $pin]}
        }
    }
    foreach source [lsort -unique $sources] {
        set root [$block findInst $source]
        set source_net [[$root findITerm Q] getNet]
        set queue [list $source_net]
        set old {}
        set sinks {}
        set seen {}
        while {[llength $queue]} {
            set net [lindex $queue 0]
            set queue [lrange $queue 1 end]
            if {[dict exists $seen [$net getName]]} {continue}
            dict set seen [$net getName] 1
            foreach sink [closure_inputs $net] {
                set inst [$sink getInst]
                set master [[$inst getMaster] getName]
                if {($master in $closure_buffer_masters) && ![closure_protected $inst] && ![llength [[[$inst findITerm X] getNet] getBTerms]]} {
                    lappend old [$inst getName]
                    lappend queue [[$inst findITerm X] getNet]
                } else {lappend sinks $sink}
            }
        }
        if {![llength $old] || [llength $sinks] < 2} {continue}
        # Keep gates, export drivers, and synchronizers; remove buffer-only chains.
        foreach name [lsort -unique $old] {unset_dont_touch [get_cells [list $name]]}
        set released {}
        foreach sink $sinks {
            set owner [$sink getInst]
            if {[$owner isDoNotTouch]} {
                lappend released [$owner getName]
                unset_dont_touch [get_cells [list [$owner getName]]]
            }
        }
        if {[llength [get_cells $old]] != [llength $old]} {error "unresolved reset buffer list"}
        # This command takes separate name arguments, not STA objects or a nested list.
        # An empty resolution causes the pinned resizer to remove ALL buffers.
        remove_buffers {*}$old
        while {[$block findInst closure_reset_${index}_leaf_0] ne {NULL}} {incr index}
        set banks [closure_banks $sinks 16 0.09]
        set leaves {}
        foreach bank $banks {
            set name closure_reset_${index}_leaf_[llength $leaves]
            set leaf [closure_buffer $name sky130_fd_sc_hs__buf_16 $source_net $bank]
            lappend leaves [$leaf findITerm A]
        }
        set root_banks [closure_banks $leaves 8 0.12]
        set ri 0
        foreach roots $root_banks {
            closure_buffer closure_reset_${index}_root_$ri sky130_fd_sc_hs__buf_16 $source_net $roots
            incr ri
        }
        foreach name [lsort -unique $released] {set_dont_touch [get_cells [list $name]]}
        closure_log [list reset_bank $source removed $old banks [llength $banks] roots [llength $root_banks] sinks [llength $sinks]]
        incr index
        incr changes
    }
    return $changes
}
proc closure_find_electrical_drivers {} {
    global closure_electrical_pins closure_decoder_outputs
    set block [ord::get_db_block]
    set outputs {}
    foreach pin $closure_electrical_pins {
        set owner [$block findInst [file dirname $pin]]
        if {$owner eq {NULL}} {continue}
        set terminal [$owner findITerm [file tail $pin]]
        if {$terminal eq {NULL} || [$terminal getNet] eq {NULL}} {continue}
        foreach driver [[$terminal getNet] getITerms] {
            if {[$driver getIoType] ne {OUTPUT}} {continue}
            set inst [$driver getInst]
            if {[closure_protected $inst] || [$inst findITerm Q] ne {NULL}} {continue}
            dict set outputs "[$inst getName]/[[$driver getMTerm] getName]" 1
        }
    }
    set closure_decoder_outputs [dict keys $outputs]
}
proc closure_decoder_banks {} {
    global closure_decoder_outputs
    set block [ord::get_db_block]
    set index 0
    foreach output $closure_decoder_outputs {
        set inst [$block findInst [file dirname $output]]
        if {$inst eq {NULL}} {error "missing decoder driver $output"}
        set net [[$inst findITerm [file tail $output]] getNet]
        set sinks [closure_inputs $net]
        if {![llength $sinks]} {continue}
        while {[$block findInst closure_decode_${index}_0] ne {NULL}} {incr index}
        set banks [closure_banks $sinks 8 0.09]
        # Split even a short fanout: these measured nets have long RC wiring.
        if {[llength $banks] == 1 && [llength $sinks] > 2} {
            set ordered [closure_sort_sinks $sinks]
            set half [expr {([llength $ordered]+1)/2}]
            set banks [list [lrange $ordered 0 $half-1] [lrange $ordered $half end]]
        }
        set bi 0
        foreach bank $banks {
            closure_buffer closure_decode_${index}_${bi} sky130_fd_sc_hs__buf_16 $net $bank
            incr bi
        }
        closure_log [list decoder_bank $output banks [llength $banks] sinks [llength $sinks]]
        incr index
    }
    return $index
}
