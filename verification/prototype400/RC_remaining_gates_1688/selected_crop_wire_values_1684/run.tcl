cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_crop_wire_values_1684}
if {[catch {
load RC_Area_Crop
scalegrid 1 2
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist on
ext2spice -o after.spice RC_Area_Crop.ext
} error]} {puts stderr $error;exit 1}
quit -noprompt
