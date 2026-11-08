"""Grid-aligned C-only exports isolate extraction and extresist augmentation effects."""
import argparse,json,os,time,re
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from compiled_charge_v2 import execute
from resources import lease,identity
from replay_keeper_flat_signed_C import MAGIC,TECH
from extract_keeper_flat_geometry_C import FLAT

def run(flat,pilot,output):
    receipts=[p/'assessment.json' for p in [flat,pilot]];a,b=[json.loads(p.read_text()) for p in receipts]
    for r in [a,b]:verify(r['input_sha256']);verify(r['artifacts'])
    if not b['native_process_completed'] or b['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('completed pilot on same flat source required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25});os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline));rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
    if not re.search(r'(?m)^\s*lambda\s+1[Ee]6\s*$',TECH.read_text()):raise ValueError('pinned non-SI technology base scale required')
    scales=[]
    for source in [flat,pilot]:
        with (source/(FLAT+'.ext')).open() as stream:
            header=[next(stream) for _ in range(8)]
        values=[line.split()[3] for line in header if line.startswith('scale ')]
        if len(values)!=1:raise ValueError('one native EXT linear scale required')
        scales.append(F(values[0])/1000000)
    if scales[0]!=scales[1] or scales[0]<=0:raise ValueError('matching positive EXT grids required')
    ratio=scales[0]
    folder=Path(__file__).resolve().parent;files=[*receipts,rc,MAGIC,TECH,Path(__file__).resolve(),folder/'compiled_charge_v2.py',folder/'replay_keeper_flat_signed_C.py',folder/'extract_keeper_flat_geometry_C.py'];cases=[]
    for name,source in [('original_EXT',flat),('pilot_EXT',pilot)]:
        ext=source/(FLAT+'.ext');target=output/(name+'.spice');script=output/(name+'.tcl')
        script.write_text(f'cd {{{source}}}\nif {{[catch {{\nextract style ngspice()\nscalegrid {ratio.numerator} {ratio.denominator}\next2spice lvs\next2spice hierarchy off\next2spice subcircuit top on\next2spice short resistor\next2spice cthresh -1e100\next2spice extresist off\next2spice -o {{{target}}} {FLAT}.ext\n}} error]}} {{puts stderr $error; exit 1}}\nquit -noprompt\n')
        files.extend([ext,script]);cases.append((name,script,target))
    pins={str(p):sha(p) for p in files};save(output/'inputs.json',dict(input_sha256=pins,fresh_native_process_per_EXT=True,explicit_grid_ratio=str(ratio),geometry_extraction_repeated=False,resistor_augmentation_enabled=False,CPU=25,memory_GiB=12,whole_cap_s=600,maximum_native_cases=2,automatic_identical_retry=False,release_ready=False));artifacts={}
    try:
        with lease(1,12,deadline):
            for name,script,target in cases:
                save(output/'status.json',dict(state='exporting_C_only_from_'+name,release_ready=False));log=output/(name+'.log');execute([MAGIC,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],log,deadline,12)
                if not target.exists() or target.stat().st_size==0:raise ValueError('completed export missing')
                artifacts.update({str(p):sha(p) for p in [target,log]})
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,two_fresh_C_only_exports_complete=True,explicit_grid_ratio=str(ratio),resistor_augmentation_enabled=False,native_simulation_allowed=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='C_only_controls_exported_comparisons_pending',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','pilot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','pilot','output']))
