cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_zero_junction_crop_1660}
if {[catch {
gds read {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_zero_junction_crop_1660/crop.gds}
load RC_Area_Crop
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract all
extresist simplify off
extresist threshold 0
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice RC_Area_Crop.ext
ext2spice extresist on
ext2spice -o after.spice RC_Area_Crop.ext
} error]} {puts stderr $error;exit 1}
quit -noprompt
