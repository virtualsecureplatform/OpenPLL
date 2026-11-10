"""Native anonymous-wire control for the opt-in reference-point candidate."""
import os,time,json
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease
from compiled_charge_v2 import execute
from audit_keeper_native_R_contraction import compare

def run():
    out=ROOT/'build/signoff400/selected_reference_point_controls_1617';out.mkdir(exist_ok=False)
    engine=ROOT/'build/tools/magic_RC_reference_point_candidate_1612'
    receipt=engine/'assessment.json';record=json.loads(receipt.read_text())
    binary=engine/'install/bin/magic';library=engine/'install/lib/magic/tcl/tclmagic.so'
    for p in [binary,library]:
        if sha(p)!=record['artifacts'][str(p)]:raise ValueError('engine changed')
    tech=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/magic/sky130A.tech')
    pins={str(p):sha(p) for p in [receipt,binary,library,tech,Path(__file__).resolve()]}
    save(out/'inputs.json',dict(input_sha256=pins,synthetic_layout=True,explicit_native_drive_annotation=True,release_ready=False))
    results=[];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    with lease(1,2,deadline):
        for enabled in [False,True]:
            case=out/('explicit' if enabled else 'default');case.mkdir()
            rc=case/'minimal.magicrc';rc.write_text(f'tech load {{{tech}}}\n')
            script=case/'run.tcl';script.write_text(r'''cd {CASE}
drc off
crashbackups disable
locking disable
load AnonymousWire
box values 0 0 4000 100
paint m1
box values 3900 -1000 4000 0
paint m1
box values 0 120 4000 220
paint m1
label B center m1
port make 1
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract all
set fh [open AnonymousWire.ext r]
set ext [read $fh]
close $fh
if {![regexp {node "([^"]*#)"} $ext unused anon]} {error "anonymous node required"}
set fh [open AnonymousWire.ext w]
foreach line [split $ext "\n"] {
    puts $fh $line
    if {[string match "node \"$anon\" *" $line]} {
        puts $fh [format {attr "%s" 10 10 11 11 m1 "res:drive"} $anon]
    }
}
close $fh
extresist include $anon
extresist simplify off
extresist threshold 0
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice AnonymousWire.ext
ext2spice extresist on
ext2spice -o after.spice AnonymousWire.ext
quit -noprompt
'''.replace('CASE',str(case)))
            cmd=['env','-u','OPENPLL_RC_EXPLICIT_COUPLING']
            if enabled:cmd+=['OPENPLL_RC_EXPLICIT_COUPLING=1']
            cmd += [str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)]
            save(out/'status.json',dict(state='running',explicit=enabled))
            execute(cmd,case/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+120),2)
            def electrical(p):
                return '\n'.join(l for l in p.read_text().splitlines() if not l.lstrip().startswith('$ **nodeattr '))
            metrics=compare(electrical(case/'before.spice'),electrical(case/'after.spice'))
            results.append(dict(explicit=enabled,**metrics))
    for p,h in pins.items():
        if sha(p)!=h:raise ValueError('input changed')
    save(out/'assessment.json',dict(input_sha256=pins,results=results,artifacts={str(p):sha(p) for p in out.glob('*/*') if p.is_file()},RC_export_fixed=False,release_ready=False))
    save(out/'status.json',dict(state='completed',release_ready=False))
if __name__=='__main__':run()
