# Implementation heuristic driven by actual extracted electrical failures.
# Preserve every sink and signal port; a strong local root isolates the logic
# driver, and spatial leaf buffers limit long-wire loading on small gates.
set block [ord::get_db_block]
set db [ord::get_db]
set targets [dict create]
foreach pair {@TARGETS@} {
    lassign $pair inst_name pin
    set inst [$block findInst $inst_name]
    if {$inst eq {NULL}} {error "missing electrical target $inst_name"}
    set term [$inst findITerm $pin]
    if {$term eq {NULL}} {error "missing electrical target pin $inst_name/$pin"}
    set net [$term getNet]
    if {$net eq {NULL}} {error "unconnected electrical target $inst_name/$pin"}
    if {[$net getSigType] ni {SIGNAL CLOCK}} {error "electrical target is not signal/clock"}
    dict set targets [$net getName] $net
}
proc clustered_buffer {name master source sinks ports x y} {
    set block [ord::get_db_block]
    set inst [odb::dbInst_create $block [[ord::get_db] findMaster $master] $name]
    set out [odb::dbNet_create $block ${name}_out]
    [$inst findITerm A] connect $source
    [$inst findITerm X] connect $out
    foreach term $sinks {$term disconnect; $term connect $out}
    foreach port $ports {$port disconnect; $port connect $out}
    $inst setLocation $x $y
    $inst setPlacementStatus PLACED
    return $out
}
set cluster_index 0
set branch_count 0
set bin_size [expr {50 * [$block getDbUnitsPerMicron]}]
foreach name [lsort [dict keys $targets]] {
    set net [dict get $targets $name]
    set drivers {}
    set sinks {}
    set clock 0
    foreach term [$net getITerms] {
        if {[$term getIoType] eq {OUTPUT}} {lappend drivers $term}
        if {[$term getIoType] eq {INPUT}} {
            lappend sinks $term
            if {[[$term getMTerm] getName] eq {CLK}} {set clock 1}
        }
    }
    if {[llength $drivers] != 1 || [llength $sinks] == 0} {
        error "unexpected electrical target topology: $name"
    }
    set ports {}
    foreach port [$net getBTerms] {
        if {[$port getIoType] ne {OUTPUT}} {error "unexpected input port on driven target"}
        lappend ports $port
    }
    lassign [[[lindex $drivers 0] getInst] getLocation] x y
    set root_master sky130_fd_sc_hs__buf_16
    if {$clock} {set root_master sky130_fd_sc_hs__clkbuf_16}
    set root [clustered_buffer electrical_root_$cluster_index $root_master $net $sinks $ports $x $y]
    set groups [dict create]
    foreach sink $sinks {
        lassign [[$sink getInst] getLocation] sx sy
        set kind data
        if {[[$sink getMTerm] getName] eq {CLK}} {set kind clock}
        set key [list [expr {$sx / $bin_size}] [expr {$sy / $bin_size}] $kind]
        dict lappend groups $key $sink
    }
    foreach key [lsort [dict keys $groups]] {
        set members [dict get $groups $key]
        for {set offset 0} {$offset < [llength $members]} {incr offset 8} {
            set chunk [lrange $members $offset [expr {$offset + 7}]]
            set sum_x 0
            set sum_y 0
            foreach sink $chunk {
                lassign [[$sink getInst] getLocation] sx sy
                incr sum_x $sx
                incr sum_y $sy
            }
            set master sky130_fd_sc_hs__buf_4
            if {[lindex $key 2] eq {clock}} {set master sky130_fd_sc_hs__clkbuf_4}
            clustered_buffer electrical_branch_$branch_count $master $root $chunk {} \
                [expr {$sum_x / [llength $chunk]}] [expr {$sum_y / [llength $chunk]}]
            incr branch_count
        }
    }
    puts "CLUSTERED_ELECTRICAL_NET name=$name sinks=[llength $sinks] clock=$clock"
    incr cluster_index
}
puts "CLUSTERED_ELECTRICAL_TOTAL roots=$cluster_index branches=$branch_count"
