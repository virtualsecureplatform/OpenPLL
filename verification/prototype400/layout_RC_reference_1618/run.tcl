cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_layout_RC_reference_1618}
if {[catch {
gds read {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_keeper_contact_corrected_C_1573/flat.gds}
load IntegerPLL_400MHz_KeeperFlatC
select top cell
extract style ngspice()
extract no resistance
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice IntegerPLL_400MHz_KeeperFlatC.ext
extresist include {a_60718_35762#}
extresist include {a_65284_57370#}
extresist simplify off
extresist extout on
extresist silent off
extresist threshold 0
extresist all
ext2spice extresist on
ext2spice -o after.spice IntegerPLL_400MHz_KeeperFlatC.ext
} error]} {puts stderr $error; exit 1}
quit -noprompt
