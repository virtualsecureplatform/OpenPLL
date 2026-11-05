"""Compare streaming sequential assessment with all retained full-array records."""
import argparse,json,os,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from common import save,sha
from resources import lease,identity
from compiled_charge import execute
from test_compiled_propagation_assessor import equal


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400'
    coverage=base/'startup_timing_characterization_coverage_002/assessment.json';c=json.loads(coverage.read_text());spec=root/'verification/signoff400/requirements.json';r=json.loads(spec.read_text());required={(k,t,1.8) for k in r['corners'] for t in r['temperatures_c']}
    source=root/'tools/sheet_charge/assess_sequential_waveform.cpp';header=root/'tools/charge_compiler/json.hpp'
    paths=[coverage,spec,source,header,Path(__file__).resolve(),root/'verification/signoff400/test_compiled_propagation_assessor.py'];datasets=[];seen=set()
    for name,digest in c['input_sha256'].items():
        if 'sequential' not in name or not name.endswith('/assessment.json'):continue
        receipt=Path(name);a=json.loads(receipt.read_text())
        if a.get('fixtures')!=108:continue
        if sha(receipt)!=digest:raise ValueError('retained sequential receipt changed')
        plan=receipt.parent.parent/'plan.json';p=json.loads(plan.read_text());pvt=p['pvt'];point=(pvt['corner'],pvt['temperature_c'],pvt['supply_v'])
        if point in seen or point not in required:raise ValueError('sequential PVT inventory')
        seen.add(point);waves=[Path(n) for n in a['artifacts'] if n.endswith('/batch.prn')]
        if len(waves)!=1:raise ValueError('unique sequential waveform')
        wave=waves[0];datasets.append((point[0]+'_'+str(point[1]),receipt,plan,wave,a,p));paths.extend([receipt,plan,wave])
    if seen!=required or len(datasets)!=15:raise ValueError('all 15 sequential points required')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=8,memory_GiB=8,deadline_uptime=deadline,native_simulations_started=0,automatic_identical_retry=False))
    def status(state,**kw):save(out/'status.json',dict(state=state,release_qualified=False,**kw))
    status('waiting_for_shared_resources')
    try:
        with lease(8,8,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            for _,receipt,plan,wave,a,p in datasets:
                if a['artifacts'][str(wave)]!=pins[str(wave)] or a['input_sha256'][str(plan)]!=pins[str(plan)]:raise ValueError('retained sequential source lineage changed')
            binary=out/'assess_sequential_waveform'
            with (out/'build.log').open('x') as log:subprocess.run(['g++','-std=c++20','-O3','-fno-fast-math','-ffp-contract=off',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            def invoke(label,plan,wave,where):
                report=where/(label+'.report.json');cfg=where/(label+'.json');save(cfg,dict(plan=str(plan),waveform=str(wave),deadline_uptime=deadline,report=str(report)));execute([binary,cfg],where/(label+'.log'),deadline,2);return report,json.loads(report.read_text())
            controls=out/'controls';controls.mkdir();plan=controls/'plan.json';save(plan,dict(fixtures=[dict(kind='clock_toggle',reset_value=0,expected_captured_values=[1,0,1,0])],waveform_columns=['V(CLK_0)','V(D_0)','V(R_0)','V(Q_0)'],stop_ns=64))
            # Physically nonpassing state data must remain a failed observation.
            wave=controls/'wrong_state.prn';wave.write_text('Index TIME V(CLK_0) V(D_0) V(R_0) V(Q_0)\n0 0 0 0 0 1.8\n1 6.4e-8 0 0 1.8 0\nEnd of Xyce(TM) Simulation\n');_,bad=invoke('wrong_state',plan,wave,controls)
            if bad['passing']!=0 or bad['records']!=[dict(case_index=0,passed=False,output_min_v=0,output_max_v=1.8,reason='DC rail, event/state or threshold correspondence failed')]:raise ValueError('nonpassing state must not be promoted')
            for label,text in [('missing_terminal',wave.read_text().replace('End of Xyce(TM) Simulation\n','')),('duplicate_terminal',wave.read_text()+'End of Xyce(TM) Simulation\n'),('nonmonotone_time',wave.read_text().replace('1 6.4e-8','1 0')),('wrong_columns',wave.read_text().replace('V(Q_0)','V(Q_1)'))]:
                path=controls/(label+'.prn');path.write_text(text);cfg=controls/(label+'.json');save(cfg,dict(plan=str(plan),waveform=str(path),deadline_uptime=deadline,report=str(controls/(label+'.report.json'))));trial=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True,timeout=30);save(controls/(label+'.result.json'),dict(returncode=trial.returncode,stderr=trial.stderr))
                if trial.returncode==0:raise ValueError('invalid waveform accepted: '+label)
            status('comparing_all_retained_sequential_records')
            def task(dataset):
                label,receipt,plan,wave,prior,p=dataset;where=out/label;where.mkdir();started=time.perf_counter();report,result=invoke('compiled',plan,wave,where);elapsed=time.perf_counter()-started
                for k in ('fixtures','passing','records','all_native_waveform_events_terminal'):equal(prior[k],result[k],label+'.'+k)
                return dict(label=label,PVT=p['pvt'],fixtures=result['fixtures'],passing=result['passing'],report=str(report),report_sha256=sha(report),elapsed_s_nonisolated=elapsed)
            with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(task,datasets))
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('sequential control source changed')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(binary):sha(binary),**{r['report']:r['report_sha256'] for r in results}},results=results,compiled_streaming_sequential_assessor_matches_all_retained_records=True,fixtures_independently_compared=sum(r['fixtures'] for r in results),required_PVT_points=15,nonpassing_state_control_preserved=True,invalid_waveform_controls_rejected=True,native_simulations_started=0,timing_observations_nonisolated=True,setup_hold_recovery_removal_qualified=False,physical_timing_qualified=False,release_qualified=False))
            status('compiled_sequential_assessor_controls_complete')
    except BaseException as e:
        status('stopped_without_promotion',reason=repr(e));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
