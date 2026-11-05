# Buffer Q loads without inserting logic between synchronizer receive stages.
proc signal_inputs {net} {
    set inputs {}
    foreach term [$net getITerms] {
        if {[$term getIoType] eq {INPUT} && [$term getSigType] in {SIGNAL CLOCK}} {
            lappend inputs $term
        }
    }
    return $inputs
}
proc new_buffer {name master source sinks} {
    set db [ord::get_db]
    set block [ord::get_db_block]
    if {[$db findMaster $master] eq {NULL}} {error "missing buffer master $master"}
    set buffer [odb::dbInst_create $block [$db findMaster $master] $name]
    set net [odb::dbNet_create $block ${name}_out]
    [$buffer findITerm A] connect $source
    [$buffer findITerm X] connect $net
    foreach term $sinks {$term disconnect; $term connect $net}
    set_dont_touch [get_cells $name]
    return $net
}
proc isolate_driver {inst name input_master output_master} {
    set block [ord::get_db_block]
    set driver [$block findInst $inst]
    if {$driver eq {NULL}} {error "missing reset driver $inst"}
    set net [[$driver findITerm Q] getNet]
    set sinks [signal_inputs $net]
    if {[llength $sinks] == 0} {error "reset source has no sinks: $inst"}
    set first [new_buffer ${name}_input $input_master $net $sinks]
    new_buffer ${name}_distribution $output_master $first $sinks
}
set block [ord::get_db_block]
set driver [$block findInst {@CLOCK_INST@}]
set net [[$driver findITerm Q] getNet]
set clocks {}
set data {}
foreach term [signal_inputs $net] {
    if {[[$term getMTerm] getName] eq {CLK}} {
        lappend clocks $term
    } else {lappend data $term}
}
if {[llength $clocks] == 0} {error "no divided-clock consumers"}
new_buffer fine_clock_input @SCL@__clkbuf_2 $net $clocks
set output [new_buffer fine_signal_output @SCL@__buf_4 $net $data]
foreach port [$net getBTerms] {$port disconnect; $port connect $output}
