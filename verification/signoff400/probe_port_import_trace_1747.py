"""Trace SPICE re-import of completed small RC output; do not rerun RC extraction."""
import json,os,time,shutil
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import identity,lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH


def run():
    base=ROOT/'build/signoff400';out=base/'selected_port_import_trace_1747';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));os.sched_setaffinity(0,{28})
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    try:
        engine=ROOT/'build/tools/magic_port_import_trace_1746';owner=json.loads((engine/'owner.json').read_text())
        save(out/'status.json',dict(state='waiting_for_verified_live_port_trace_build'))
        while not (engine/'assessment.json').exists():
            if identity(owner['pid'])!=owner['birth']:raise ValueError('build ended without receipt')
            if json.loads((engine/'status.json').read_text())['state']=='stopped_without_qualification':raise ValueError('build failed')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('build observation deadline')
            time.sleep(5)
        source=base/'selected_rebuilt_ports_RC_1742';receipt=source/'native_completion.json';record=json.loads(receipt.read_text())
        worker=json.loads((source/'native.process.json').read_text())
        if not record['native_process_completed'] or identity(worker['pid'])==worker['birth']:raise ValueError('completed native data required')
        for name,digest in {**record['input_sha256'],**record['artifacts']}.items():
            if sha(name)!=digest:raise ValueError('completed source changed')
        binary,library=engine/'install/bin/magic',engine/'install/lib/magic/tcl/tclmagic.so'
        er=engine/'assessment.json';data=json.loads(er.read_text())
        for p in [binary,library]:
            if data['artifacts'][str(p)]!=sha(p):raise ValueError('engine changed')
        for name in ['RotatedCrop.ext','RotatedCrop.res.ext']:shutil.copyfile(source/name,out/name)
        rc=out/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        script=out/'run.tcl';script.write_text(f'''cd {{{out}}}
if {{[catch {{
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist on
ext2spice -o traced.spice RotatedCrop.ext
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
        paths=[receipt,er,binary,library,TECH,rc,script,Path(__file__).resolve(),out/'RotatedCrop.ext',out/'RotatedCrop.res.ext']
        pins={str(p):sha(p) for p in paths}
        save(out/'inputs.json',dict(input_sha256=pins,R_extraction_invoked=False,completed_failed_port_case_reused_for_diagnosis_only=True))
        with lease(1,4,deadline):
            save(out/'status.json',dict(state='native_port_import_trace_running'))
            execute(['env','OPENPLL_RC_NATIVE_CAPS=1','OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_ZERO_JUNCTION=1',
                'OPENPLL_RC_PORT_IMPORT_TRACE=1','OPENPLL_RC_PORT_REBUILD_TRACE=1',str(binary),'-nowrapper','-dnull','-noconsole',
                '-rcfile',str(rc),str(script)],out/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+60),4)
        for p,digest in pins.items():
            if sha(p)!=digest:raise ValueError('input changed')
        traces=[s for s in (out/'native.log').read_text().splitlines() if s.startswith('OPENPLL_RC_PORT_IMPORT') and any(n in s for n in ['name=ALIAS_DRIVE ','name=a_106400_64915# '])]
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/n):sha(out/n) for n in ['traced.spice','native.log']},
            native_process_completed=True,observations=traces,R_extraction_invoked=False,RC_export_fixed=False,release_ready=False))
        save(out/'status.json',dict(state='native_port_import_trace_complete'))
        print('\n'.join(traces))
    except BaseException as error:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(error)));raise

if __name__=='__main__':run()
