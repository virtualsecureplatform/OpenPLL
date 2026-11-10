cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_killed_coupling_export_1611}
if {[catch {
load KilledCoupling
ext2spice lvs
ext2spice hierarchy off
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice KilledCoupling.ext
ext2spice extresist on
ext2spice -o after.spice KilledCoupling.ext
} error]} {puts stderr $error; exit 1}
quit -noprompt
