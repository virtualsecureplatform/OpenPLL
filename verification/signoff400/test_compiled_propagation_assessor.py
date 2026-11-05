"""Check streaming assessment against retained independent full-array results."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import subprocess
import time
from common import save,sha
from compiled_charge import execute
from resources import lease


def equal(a,b,path='root'):
    if isinstance(a,dict):
        if set(a)!=set(b):raise ValueError(f'keys differ at {path}: {set(a)^set(b)}')
        for k in a:equal(a[k],b[k],path+'.'+k)
    elif isinstance(a,list):
        if len(a)!=len(b):raise ValueError('list length differs at '+path)
        for i,(x,y) in enumerate(zip(a,b)):equal(x,y,f'{path}[{i}]')
    elif isinstance(a,(int,float)) and not isinstance(a,bool):
        if not math.isclose(a,b,rel_tol=2e-14,abs_tol=1e-12):raise ValueError(f'value differs at {path}: {a} {b}')
    elif a!=b:raise ValueError('value differs at '+path)


def run(output):
    output.mkdir(parents=True,exist_ok=False);root=Path.cwd();source=root/'tools/sheet_charge/assess_propagation_waveform.cpp';header=root/'tools/charge_compiler/json.hpp'
    campaign=root/'build/signoff400/startup_timing_mux2_4_15PVT_raw_001/assessment.json';new=json.loads(campaign.read_text())
    if new['completed_raw_PVT_points']!=15 or not new['all_raw_fixture_events_pass']:raise ValueError('complete new native grid required')
    datasets=[]
    for result in new['case_results']:
        receipt=Path(result['assessment']);plan=receipt.parent.parent/'plan.json';wave=receipt.parent/'batch.prn'
        if sha(receipt)!=result['assessment_sha256']:raise ValueError('new raw receipt changed')
        datasets.append((result['label'],plan,receipt,wave))
    old=root/'build/timing400/release_001/compact_propagation_tt27_001';datasets.append(('legacy_891',old/'plan.json',old/'run_001/assessment.json',old/'run_001/batch.prn'))
    paths=[campaign,source,header,Path(__file__).resolve(),*[p for _,*items in datasets for p in items]]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(8,8,deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
        binary=output/'assess_propagation_waveform'
        with (output/'build.log').open('x') as log:
            subprocess.run(['g++','-std=c++20','-O3','-fno-fast-math','-ffp-contract=off',str(source),'-o',str(binary)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        results=[]
        def task(dataset):
            label,plan,receipt,wave=dataset;prior=json.loads(receipt.read_text());where=output/label;where.mkdir()
            if prior['artifacts'][str(wave)]!=pins[str(wave)]:raise ValueError('native waveform changed')
            cfg=where/'config.json';report=where/'report.json';save(cfg,dict(plan=str(plan),waveform=str(wave),deadline_uptime=deadline,report=str(report)))
            start=time.perf_counter();execute([binary,cfg],where/'run.log',deadline,2);elapsed=time.perf_counter()-start
            result=json.loads(report.read_text())
            for k in ('fixtures','passing','strict_output_slew_passing','records','all_native_waveform_events_terminal'):equal(prior[k],result[k],label+'.'+k)
            return dict(label=label,fixtures=result['fixtures'],strict_slew_nonpassing=result['fixtures']-result['strict_output_slew_passing'],elapsed_s_nonisolated=elapsed,report=str(report),report_sha256=sha(report))
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(task,datasets))
        # Missing native terminal marker must fail rather than silently assess partial data.
        fixture=output/'missing_terminal.prn';fixture.write_text('Index TIME V(IN_0) V(OUT_0)\n0 0 0 0\n1 3.4e-8 0 0\n')
        plan=output/'control_plan.json';save(plan,dict(fixtures=[dict(inverted=False)]));cfg=output/'negative.json'
        save(cfg,dict(plan=str(plan),waveform=str(fixture),deadline_uptime=deadline,report=str(output/'negative.report.json')))
        bad=subprocess.run([str(binary),str(cfg)],capture_output=True,text=True)
        save(output/'negative.result.json',dict(returncode=bad.returncode,stderr=bad.stderr))
        if bad.returncode==0:raise ValueError('partial waveform accepted')
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha,map(Path,pins)))!=list(pins.values()):raise ValueError('source changed during assessor controls')
        artifacts={str(binary):sha(binary),**{r['report']:r['report_sha256'] for r in results}}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
             compiled_streaming_assessor_matches_retained_python_records=True,fixtures_independently_compared=sum(r['fixtures'] for r in results),
             nonpassing_slew_records_preserved=True,missing_terminal_marker_rejected=True,
             timing_measurements_are_nonisolated=True,physical_timing_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
