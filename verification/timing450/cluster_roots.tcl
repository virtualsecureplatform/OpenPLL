# Keep the retimer's two isolation buffers physically close to its Q pin.
# Logical dont_touch does not constrain placement; long Q wiring defeats
# load isolation after extraction.
set block [ord::get_db_block]
set source [$block findInst {@CLOCK_INST@}]
set signal [$block findInst fine_signal_output]
unset_dont_touch [get_cells fine_signal_output]
replace_cell fine_signal_output @SCL@__buf_16
set_dont_touch [get_cells fine_signal_output]
detailed_placement
lassign [$source getLocation] root_x root_y
set first [$block findInst fine_clock_input]
set source_width [[$source getMaster] getWidth]
set first_width [[$first getMaster] getWidth]
set signal_width [[$signal getMaster] getWidth]
set left [expr {$root_x + $source_width}]
if {$left + $first_width + $signal_width > [[$block getCoreArea] xMax]} {
    set left [expr {$root_x - $first_width - $signal_width}]
}
if {$left < [[$block getCoreArea] xMin]} {error "no room for retimer isolation cluster"}
$source setPlacementStatus LOCKED
$first setPlacementStatus PLACED
$signal setPlacementStatus PLACED
$first setLocation $left $root_y
$signal setLocation [expr {$left + $first_width}] $root_y
detailed_placement -max_displacement {10 10}
$first setPlacementStatus LOCKED
$signal setPlacementStatus LOCKED
# Allow hold repair to attach data-delay cells at the retimer D pin. Its
# master remains protected by dont_touch; locking the FF itself makes the
# pinned resizer attempt an empty load set.
$source setPlacementStatus PLACED
check_placement -verbose
puts "RETIMER_CLUSTER source=[$source getLocation] input=[$first getLocation] output=[$signal getLocation]"
