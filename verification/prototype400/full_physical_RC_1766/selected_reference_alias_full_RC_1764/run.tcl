cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_reference_alias_full_RC_1764}
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
extresist simplify off
extresist extout on
extresist silent off
extresist threshold 0
extresist all
ext2spice extresist on
ext2spice -o after.spice IntegerPLL_400MHz_KeeperFlatC.ext
feedback save feedback.txt
} error]} {puts stderr $error;exit 1}
quit -noprompt
