cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_ground_copy_driver_1725}
if {[catch {
gds read {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_keeper_contact_corrected_C_1573/flat.gds}
load IntegerPLL_400MHz_KeeperFlatC
select top cell
extract style ngspice()
extract no resistance
extresist simplify off
extresist threshold 0
extresist include VGND
extresist all
} error]} {puts stderr $error;exit 1}
quit -noprompt
