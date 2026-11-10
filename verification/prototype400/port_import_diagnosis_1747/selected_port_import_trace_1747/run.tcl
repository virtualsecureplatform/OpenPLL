cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_port_import_trace_1747}
if {[catch {
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist on
ext2spice -o traced.spice RotatedCrop.ext
} error]} {puts stderr $error;exit 1}
quit -noprompt
