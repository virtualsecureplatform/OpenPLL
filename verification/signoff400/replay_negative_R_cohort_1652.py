"""Bounded two-net native RC candidate pilot on the unchanged checked layout."""
import os,json,time,shutil
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from extract_keeper_flat_geometry_C import FLAT

def run():
    out=ROOT/'build/signoff400/selected_negative_R_cohort_replay_1652';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        engine=ROOT/'build/tools/magic_canonical_RC_1646'
        build_owner=json.loads((engine/'owner.json').read_text())
        observation_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
        save(out/'status.json',dict(state='waiting_for_live_diagnostic_build',release_ready=False))
        while not (engine/'assessment.json').exists():
            if (engine/'status.json').exists() and json.loads((engine/'status.json').read_text())['state']=='stopped_without_qualification':raise RuntimeError('diagnostic build failed')
            if identity(build_owner['pid'])!=build_owner['birth']:raise RuntimeError('diagnostic build stopped without receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>observation_deadline:raise TimeoutError('build observation deadline')
            time.sleep(10)
        source=ROOT/'build/signoff400/selected_keeper_contact_corrected_C_1573'
        binary=engine/'install/bin/magic';library=engine/'install/lib/magic/tcl/tclmagic.so'
        receipts=[engine/'assessment.json',source/'assessment.json']
        for receipt in receipts:
            r=json.loads(receipt.read_text())
            for p,h in r['artifacts'].items():
                if sha(p)!=h:raise ValueError('artifact changed: '+p)
        gds=source/'flat.gds';ext=source/(FLAT+'.ext');local=out/ext.name
        shutil.copyfile(ext,local)
        rc=out/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        cohort_receipt=ROOT/'build/signoff400/selected_negative_R_cohort_1651/assessment.json'
        cohort=json.loads(cohort_receipt.read_text())
        if not cohort['all_negative_native_rnodes_bound']:raise ValueError('complete negative-R ownership required')
        wanted=cohort['requested_nets']
        selection='\n'.join('extresist include {'+n+'}' for n in wanted)
        script=out/'run.tcl';script.write_text(f'''cd {{{out}}}
if {{[catch {{
gds read {{{gds}}}
load {FLAT}
select top cell
extract style ngspice()
extract no resistance
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice {FLAT}.ext
{selection}
extresist simplify off
extresist extout on
extresist silent off
extresist threshold 0
extresist all
ext2spice extresist on
ext2spice -o after.spice {FLAT}.ext
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
        pins={str(p):sha(p) for p in [*receipts,cohort_receipt,binary,library,gds,ext,TECH,rc,script,Path(__file__).resolve()]}
        save(out/'inputs.json',dict(input_sha256=pins,requested_nets=wanted,explicit_coupling=True,source_EXT_reused_without_reextraction=True,maximum_native_cases=1,automatic_identical_retry=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        os.sched_setaffinity(0,{29})
        save(out/'status.json',dict(state='waiting_for_resources',release_ready=False))
        with lease(1,12,deadline):
            save(out/'status.json',dict(state='native_negative_R_cohort_running',release_ready=False))
            execute(['env','OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_AREA_DIAGNOSTIC=1','OPENPLL_RC_NATIVE_CAPS=1',str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],out/'native.log',deadline,12)
        for p,h in pins.items():
            if sha(p)!=h:raise ValueError('input changed: '+p)
        if sha(local)!=sha(ext):raise ValueError('native source EXT changed')
        paths=[out/'before.spice',out/'after.spice',out/(FLAT+'.res.ext'),out/'native.log']
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in paths},native_process_completed=True,conservation_verified=False,RC_export_fixed=False,release_ready=False))
        save(out/'status.json',dict(state='native_pilot_completed_audit_pending',release_ready=False))
    except BaseException as e:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise
if __name__=='__main__':run()
