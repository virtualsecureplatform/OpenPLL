cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_reference_point_controls_1617/default}
drc off
crashbackups disable
locking disable
load AnonymousWire
box values 0 0 4000 100
paint m1
box values 3900 -1000 4000 0
paint m1
box values 0 120 4000 220
paint m1
label B center m1
port make 1
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract all
set fh [open AnonymousWire.ext r]
set ext [read $fh]
close $fh
if {![regexp {node "([^"]*#)"} $ext unused anon]} {error "anonymous node required"}
set fh [open AnonymousWire.ext w]
foreach line [split $ext "\n"] {
    puts $fh $line
    if {[string match "node \"$anon\" *" $line]} {
        puts $fh [format {attr "%s" 10 10 11 11 m1 "res:drive"} $anon]
    }
}
close $fh
extresist include $anon
extresist simplify off
extresist threshold 0
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice AnonymousWire.ext
ext2spice extresist on
ext2spice -o after.spice AnonymousWire.ext
quit -noprompt
