"""Compare cached/uncached selected RTL traces, plus cache rejection controls.

Measured packets test actual unsupported-code trajectories. Explicit synthetic
fixtures exercise full recovery epochs; they never enter a calibration registry.
"""
import argparse,copy,json,os,shutil,subprocess,sys,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_model_registry import validate
from selected_mixed_signal_build_cache_v2 import load
from resources import identity,lease

TRACES=('controls.csv','edges.csv','segments.csv','reference_phase.json','dco_table.txt','dco_frequency_model.json','run.log')

def run(registry,detector,clock,cache,output):
    os.sched_setaffinity(0,{16});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    r=validate(json.loads(registry.read_text()));points=[p for p in r['points']if p['coarse']==20]
    seed=min(points,key=lambda p:(abs(p['frequency_hz']-400e6),p['fine']))['fine']
    folder=Path(__file__).resolve().parent
    sources=[registry,detector,clock,cache/'assessment.json',Path(__file__).resolve(),folder/'run_selected_mixed_signal_v5.py',folder/'run_selected_mixed_signal_v6.py',folder/'selected_mixed_signal_build_cache_v2.py',folder/'common_v3.py',folder/'resources.py']
    pins={str(p):sha(p)for p in sources};pins.update(load(cache,detector));records=[];artifacts={}
    fixture=output/'synthetic_tuning_fixture';fixture.mkdir();synthetic=[]
    for code in range(8,248):
        p=fixture/f'point_{code}.json';save(p,dict(synthetic=True,fixture_only=True,not_native_measurement=True,
            coarse_code=dict(window_codes=[20]),dco_code=dict(window_codes=[code]),
            signals={'v(pllout)':dict(rising_edges_200_260ns=24,mean_frequency_mhz=400+(code-128)*.25)}))
        synthetic.append(p);pins[str(p)]=sha(p)
    cases=[('measured_phase0',0,0,[Path(p['receipt'])for p in points],seed,False),
           ('measured_phase20',0,20,[Path(p['receipt'])for p in points],seed,False),
           ('synthetic_disable',1,0,synthetic,128,True),('synthetic_tracking_reset',2,20,synthetic,128,True)]
    for index,(name,scenario,phase,receipts,start,synthetic_case)in enumerate(cases):
        case_results={};where={}
        for mode in (('uncached','cached')if index%2==0 else ('cached','uncached')):
            dest=output/(name+'_'+mode);runner=folder/f'run_selected_mixed_signal_v{6 if mode=="cached"else 5}.py'
            command=[sys.executable,runner,'--detector',detector,'--clock-timing',clock,'--output',dest,
                     '--coarse',20,'--seed',start,'--ki',4,'--kp',0,'--scenario',scenario,'--phase-ns',phase,'--interpolation','linear_period']
            if mode=='cached':command+=['--build-cache',cache]
            for receipt in receipts:command+=['--point',receipt]
            save(output/'status.json',dict(state='cache_trace_regression_running',case=name,mode=mode,completed_pairs=len(records),release_ready=False))
            begin=time.monotonic()
            with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+240):
                with (output/(dest.name+'.log')).open('x')as log:
                    result=subprocess.run(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT,timeout=180)
            elapsed=time.monotonic()-begin
            if result.returncode not in (0,1,3)or not(dest/'assessment.json').exists():raise ValueError('runner stopped without diagnostic assessment')
            report=json.loads((dest/'assessment.json').read_text());case_results[mode]=(elapsed,report);where[mode]=dest
        a,b=[case_results[m][1]for m in ('uncached','cached')]
        scrub=lambda v:{k:x for k,x in v.items()if k not in ('elapsed_s','compiled_build_reused')}
        if scrub(a)!=scrub(b):raise ValueError('cached/uncached diagnostic assessment differs')
        if b.get('compiled_build_reused')is not True:raise ValueError('cache path was not exercised')
        for filename in TRACES:
            if sha(where['uncached']/filename)!=sha(where['cached']/filename):raise ValueError('trace differs: '+filename)
        if synthetic_case and (a['native_exit']!=0 or not a['terminal_marker_present']or a['measurement_requests']or len(a['initializations'])!=2):
            raise ValueError('synthetic regression must exercise both complete recovery epochs')
        for dest in where.values():
            for filename in (*TRACES,'assessment.json','inputs.json'):
                p=dest/filename;artifacts[str(p)]=sha(p)
        records.append(dict(case=name,scenario=scenario,phase_ns=phase,synthetic_fixture=synthetic_case,
            all_trace_files_byte_identical=True,assessments_equivalent=True,state=a['state'],
            uncached_wall_s=case_results['uncached'][0],cached_wall_s=case_results['cached'][0]))
    # Mutate only fresh copies. Never change the pinned original cache or RTL.
    negatives=[];original=json.loads((cache/'assessment.json').read_text())
    for kind in ('artifact_bytes','detector_identity','image_fingerprint'):
        mutant=output/('reject_'+kind);mutant.mkdir();record=copy.deepcopy(original)
        for filename in ('loop.vvp','phase_clock_vpi.vpi'):shutil.copy2(cache/filename,mutant/filename)
        record['artifacts']={str(mutant/Path(p).name):digest for p,digest in original['artifacts'].items()}
        save(mutant/'assessment.json',record);load(mutant,detector)
        if kind=='artifact_bytes':
            with(mutant/'loop.vvp').open('ab')as stream:stream.write(b'\n# changed artifact\n')
        elif kind=='detector_identity':record['build_inputs'][str(detector)]='0'*64
        else:record['image_fingerprint'][-1]+=1
        save(mutant/'assessment.json',record)
        try:load(mutant,detector)
        except ValueError as error:negatives.append(dict(control=kind,rejected=True,reason=str(error)))
        else:raise ValueError('cache mutation was accepted: '+kind)
        artifacts[str(mutant/'assessment.json')]=sha(mutant/'assessment.json')
    verify(pins);verify(artifacts)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,records=records,negative_controls=negatives,
        every_trace_byte_identical=True,synthetic_fixtures_entered_calibration_registry=False,
        paired_uncached_wall_s=sum(r['uncached_wall_s']for r in records),paired_cached_wall_s=sum(r['cached_wall_s']for r in records),
        timing_scope='sequential alternating pairs on physical CPU16 under concurrent native host load; cache creation is separate',
        scope='Build-cache equivalence only. Actual measured unsupported-code prefixes and synthetic complete recovery trajectories; no PLL functional or physical-model qualification.',
        release_ready=False))
    save(output/'status.json',dict(state='cache_trace_regression_complete',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('registry','detector','clock','cache','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    try:run(*(getattr(a,n).resolve()for n in ('registry','detector','clock','cache','output')))
    except BaseException as error:
        if a.output.exists():save(a.output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise
