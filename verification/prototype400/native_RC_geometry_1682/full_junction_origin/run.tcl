cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_zero_junction_origins_1659}
if {[catch {
scalegrid 1 2
load IntegerPLL_400MHz_KeeperFlatC
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh 1e100
ext2spice extresist off
ext2spice -o devices.spice IntegerPLL_400MHz_KeeperFlatC.ext
} error]} {puts stderr $error;exit 1}
quit -noprompt
