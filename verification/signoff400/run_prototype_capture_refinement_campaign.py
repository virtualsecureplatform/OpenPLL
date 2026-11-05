"""Run off-grid capture refinement across the used flip-flop masters and process corners."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity
from compiled_charge import execute
from run_prototype_capture_refinement import LOADS


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    worker=Path(__file__).with_name('run_prototype_capture_refinement.py').resolve()
    pins={str(p):sha(p) for p in (worker,Path(__file__).resolve())}
    pilot=ROOT/'build/signoff400/prototype_v3_capture_refinement_tt_dfrtp1_001';pilot_receipt=pilot/'assessment.json'
    p=json.loads(pilot_receipt.read_text());verify(p['input_sha256']);verify(p['artifacts'])
    if p['corner']!='tt' or p['master']!='sky130_fd_sc_hs__dfrtp_1' or not p['all_pretest_states_verified']:raise ValueError('matching completed pilot required')
    points=[(c,m) for c in ('tt','ff','ss','sf','fs') for m in LOADS];save(output/'status.json',dict(state='capture_refinement_campaign_running',points=25,release_ready=False))
    def point(case):
        c,m=case
        if case==('tt','dfrtp_1'):return dict(corner=c,master=m,directory=str(pilot),reused=True)
        where=output/(c+'_'+m);log=output/(c+'_'+m+'.log')
        execute([sys.executable,worker,'--output',where,'--corner',c,'--master',m],log,deadline,4)
        return dict(corner=c,master=m,directory=str(where),reused=False)
    with ThreadPoolExecutor(max_workers=4) as pool:records=list(pool.map(point,points))
    passing=0;artifacts={}
    for row in records:
        rp=Path(row['directory'])/'assessment.json';r=json.loads(rp.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r['corner']!=row['corner'] or r['master']!='sky130_fd_sc_hs__'+row['master'] or r['cases']!=24:raise ValueError('capture-refinement operating point mismatch')
        if r['input_sha256'][str(worker)]!=pins[str(worker)]:raise ValueError('capture refinement worker changed')
        row['assessment_sha256']=sha(rp);row['all_pretest_states_verified']=r['all_pretest_states_verified'];passing+=int(r['all_pretest_states_verified']);pins[str(rp)]=sha(rp)
    detail=output/'points.json';save(detail,records);artifacts[str(detail)]=sha(detail);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,complete_master_corner_grids=len(records),native_cases=600,
        all_pretest_states_verified=passing==25,passing_grids=passing,
        final_load_and_slew_envelope_verified=False,all_clock_domains_and_startup_frequencies_covered=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='capture_refinement_campaign_complete',complete_grids=len(records),passing_grids=passing,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
