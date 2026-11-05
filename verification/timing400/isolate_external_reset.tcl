# Keep external RESET_N on simple buffer input pins and give each receiver
# a short private connection. This changes physical reset delay, so actual
# reset/interface bounds must be rechecked before any candidate adoption.
set block [ord::get_db_block]
set db [ord::get_db]
set source [$block findNet RESET_N]
if {$source eq {NULL}} {error "missing external RESET_N net"}
set sinks [$source getITerms]
if {[llength $sinks] != 6} {error "unexpected external reset receiver count"}
foreach sink $sinks {
    set pin [[$sink getMTerm] getName]
    set master [[[$sink getInst] getMaster] getName]
    if {[$sink getIoType] ne {INPUT} || $pin ni {RESET_B SET_B}
        || ![regexp {^sky130_fd_sc_hs__df[rs]tp_[124]$} $master]} {
        error "unexpected external reset receiver type"
    }
}
set index 0
foreach sink $sinks {
    set name external_reset_leaf_$index
    if {[$block findInst $name] ne {NULL}} {error "external reset already isolated"}
    set leaf [odb::dbInst_create $block [$db findMaster sky130_fd_sc_hs__buf_4] $name]
    set output [odb::dbNet_create $block ${name}_out]
    [$leaf findITerm A] connect $source
    [$leaf findITerm X] connect $output
    lassign [[$sink getInst] getLocation] x y
    puts "ISOLATED_EXTERNAL_RESET receiver=[[$sink getInst] getName]/[[$sink getMTerm] getName] buffer=$name"
    $sink disconnect
    $sink connect $output
    $leaf setLocation $x $y
    $leaf setPlacementStatus PLACED
    incr index
}
set_dont_touch [get_cells external_reset_leaf_*]
puts "EXTERNAL_RESET_ISOLATION receivers=$index"
