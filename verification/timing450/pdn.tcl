# Logical constants have only signal sinks; map them to powered tie cells.
# OpenDB global_connect skips protected instances. Protection is restored
# after connecting supply pins; signal nets are unchanged by this operation.
unset_dont_touch [get_cells *]
set block [ord::get_db_block]
set master [[ord::get_db] findMaster @SCL@__conb_1]
foreach {name output} {one_ HI zero_ LO} {
    set net [$block findNet $name]
    if {$net eq {NULL}} {continue}
    foreach term [$net getITerms] {
        if {[$term getSigType] ne {SIGNAL}} {error "constant net has non-signal sink"}
    }
    set sinks [$net getITerms]
    set tie [odb::dbInst_create $block $master "constant_tie_$output"]
    $tie setLocation {*}[[[lindex $sinks 0] getInst] getLocation]
    $tie setPlacementStatus PLACED
    $net setSigType SIGNAL
    [$tie findITerm $output] connect $net
}
repair_tie_fanout @SCL@__conb_1/HI
repair_tie_fanout @SCL@__conb_1/LO
tapcell -tapcell_master @SCL@__tapvpwrvgnd_1 -endcap_master @SCL@__decap_@DECAP@ -distance 10
detailed_placement
filler_placement {@SCL@__fill_8 @SCL@__fill_4 @SCL@__fill_2 @SCL@__fill_1}
check_placement -verbose
add_global_connection -net VDD -inst_pattern {.*} -pin_pattern {^(VPWR|VPB)$} -power
add_global_connection -net VSS -inst_pattern {.*} -pin_pattern {^(VGND|VNB)$} -ground
global_connect
set_dont_touch [get_cells {fine_clock_input fine_signal_output reset_root_* @CLOCK_INST@}]
set_voltage_domain -name CORE -power VDD -ground VSS
define_pdn_grid -name core_grid -voltage_domains CORE -pins {met4 met5}
add_pdn_ring -grid core_grid -layers {met4 met5} -widths 2 -spacings 2 -core_offsets 2
add_pdn_stripe -grid core_grid -layer met1 -width 0.48 -followpins -extend_to_core_ring
add_pdn_stripe -grid core_grid -layer met4 -width 2 -pitch 40 -offset 10 -extend_to_core_ring
add_pdn_stripe -grid core_grid -layer met5 -width 2 -pitch 40 -offset 10 -extend_to_core_ring
add_pdn_connect -grid core_grid -layers {met1 met4}
add_pdn_connect -grid core_grid -layers {met4 met5}
pdngen -failed_via_report @ROOT@/pdn_filled_failed_vias.rpt
set total 0
set connected 0
foreach inst [[ord::get_db_block] getInsts] {
    foreach term [$inst getITerms] {
        if {[$term getSigType] in {POWER GROUND}} {
            incr total
            if {[$term getNet] ne {NULL}} {incr connected}
        }
    }
}
puts "POWER_PIN_AUDIT total=$total connected=$connected"

if {$connected != $total} {error "unconnected power pins"}
write_db @ROOT@/pdn.odb
write_def @ROOT@/pdn.def
check_power_grid -net VDD -error_file @ROOT@/pdn_filled_vdd_errors.rpt
check_power_grid -net VSS -error_file @ROOT@/pdn_filled_vss_errors.rpt
