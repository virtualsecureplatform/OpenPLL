cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_wire_R_units_1676}
if {[catch {
load WireUnits
extract style ngspice()
ext2spice lvs
ext2spice cthresh 1e100
ext2spice extresist on
ext2spice -o wire.spice WireUnits.ext
} error]} {puts stderr $error;exit 1}
quit -noprompt
