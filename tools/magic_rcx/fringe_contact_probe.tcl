# Diagnostic geometry only; deliberately no DRC/signoff claim.
# Run each contact/shield pair in a fresh directory and native process.
foreach setting {OPENPLL_PROBE_DIRECTORY OPENPLL_PROBE_CONTACT OPENPLL_PROBE_SHIELD} {
    if {![info exists env($setting)]} {error "Missing $setting"}
}
cd $env(OPENPLL_PROBE_DIRECTORY)
if {[file exists FringeContactProbe.ext]} {error "Fresh directory required"}
if {$env(OPENPLL_PROBE_CONTACT) ni {0 1} || $env(OPENPLL_PROBE_SHIELD) ni {0 1}} {
    error "Contact and shield settings must be 0 or 1"
}
if {[catch {
    load FringeContactProbe
    box values 0 0 400 400
    paint m3
    label SOURCE center m3
    if {$env(OPENPLL_PROBE_CONTACT)} {
        box values 320 40 400 360
        paint via3
    }
    box values 420 0 1000 400
    paint m1
    label TARGET center m1
    if {$env(OPENPLL_PROBE_SHIELD)} {
        box values 460 80 540 320
        paint m2
        label SHIELD center m2
    }
    extract style ngspice()
    extract do local
    extract do capacitance
    extract do coupling
    extract no resistance
    extract all
    ext2spice lvs
    ext2spice hierarchy off
    ext2spice cthresh -1e100
    ext2spice -o probe.spice FringeContactProbe.ext
    save FringeContactProbe
} message]} {puts stderr $message; exit 1}
quit -noprompt
