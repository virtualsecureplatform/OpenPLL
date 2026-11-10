cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_reference_alias_separated_1761}
if {[catch {
gds read {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_drive_type_RC_controls_1729/rotation0.gds}
load RotatedCrop
select top cell
extract style ngspice()
extract no resistance
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice RotatedCrop.ext
extresist simplify off
extresist threshold 0
extresist include ALIAS_DRIVE
extresist all
ext2spice extresist on
ext2spice -o after.spice RotatedCrop.ext
} error]} {puts stderr $error;exit 1}
quit -noprompt
