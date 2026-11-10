cd {/home/work-bleaker/kmatsuoka/sources/OpenPLL/build/signoff400/selected_indexed_repeated_labels_1710/magic_single_RC_points_1704_repeat1}
# Run in a fresh output directory using the SKY130 Magic technology.
# OPENPLL_TEST_COUPLING=1 (default) reproduces the extra substrate capacitance;
# OPENPLL_TEST_COUPLING=0 is the negative control.  This is not a signoff deck.
set coupling 1
if {[info exists env(OPENPLL_TEST_COUPLING)]} {
    set coupling $env(OPENPLL_TEST_COUPLING)
}
if {$coupling ni {0 1}} {puts stderr "OPENPLL_TEST_COUPLING must be 0 or 1"; exit 1}
if {[file exists before.spice] || [file exists after.spice]} {
    puts stderr "Use a fresh output directory"; exit 1
}
drc off
crashbackups disable
locking disable
if {[catch {
load OpenPLL_Coupling_R_Probe
box values 0 0 4000 100
paint m1
box values 0 0 20 100
label A center m1
port make 1
box values 3980 0 4000 100
label AFAR center m1
port make 3
box values 0 120 4000 220
paint m1
label B center m1
port make 2
box values 1200 0 1220 100
label MID center m1
box values 2700 0 2720 100
label MID center m1
extract style ngspice()
extract do local
extract do capacitance
if {$coupling} {extract do coupling} else {extract no coupling}
extract no resistance
extract warn all
extresist simplify off
extresist threshold 0
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice OpenPLL_Coupling_R_Probe.ext
extresist all
ext2spice extresist on
ext2spice -o after.spice OpenPLL_Coupling_R_Probe.ext
feedback save feedback.txt
} error]} {puts stderr $error; exit 1}
quit -noprompt
