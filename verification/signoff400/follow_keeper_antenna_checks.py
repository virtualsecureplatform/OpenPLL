"""Follow one keeper antenna run with independent mask/contact/process checks."""
import argparse,json,os,time,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from common_v3 import ROOT,save,sha,verify
from resources import identity
from compiled_charge import execute


def run(parent,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{30})
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400;owner=json.loads((parent/'owner.json').read_text())
    folder=Path(__file__).resolve().parent;engine=ROOT/'build/signoff400/selected_magic_conservative_contact_controls_650/assessment.json'
    control=ROOT/'build/signoff400/selected_M5_fill_alias_control_555'
    scripts=[folder/n for n in ['check_prototype_flat_antenna_geometry_v2.py','check_selected_contact_paint_containment.py','check_selected_antenna_process_prefix_v3.py','audit_keeper_antenna_process_views.py']]
    pins={str(p):sha(p)for p in [Path(__file__).resolve(),parent/'owner.json',parent/'input_manifest.json',engine,control/'assessment.json',*scripts]}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'inputs.json',dict(input_sha256=pins,original_parent_owner=owner,total_cap_s=86400,max_parallel_process_views=2,automatic_identical_retry=False,release_ready=False))
    def invoke(script,args,log):
        verify(pins);execute([sys.executable,script,*args],log,deadline,20)
    try:
        while not (parent/'assessment.json').exists():
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('original antenna run stopped without assessment')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('antenna observation limit; original job untouched')
            save(output/'status.json',dict(state='waiting_for_original_keeper_antenna',release_ready=False));time.sleep(15)
        native=json.loads((parent/'assessment.json').read_text());verify(native['input_sha256']);verify(native['artifacts'])
        save(output/'status.json',dict(state='keeper_mask_geometry_check_running',release_ready=False))
        invoke(scripts[0],['--source',parent,'--control',control,'--output',output/'geometry'],output/'geometry.log')
        save(output/'status.json',dict(state='keeper_contact_paint_check_running',release_ready=False))
        invoke(scripts[1],['--parent',parent,'--output',output/'paint'],output/'paint.log')
        g=json.loads((output/'geometry/assessment.json').read_text());p=json.loads((output/'paint/assessment.json').read_text())
        for r in [g,p]:verify(r['input_sha256']);verify(r['artifacts'])
        if not all(g[k]for k in ['all_checked_mask_regions_preserved','extracted_MOS_gate_area_matches_source_poly_diff_intersection','source_and_flat_channel_areas_match'])or not p['all_six_actual_contact_masks_contained_by_paint']:
            raise ValueError('native geometry/contact comparison failed')
        if native['native_antenna_feedback_entries']:
            save(output/'status.json',dict(state='nonzero_parent_antenna_feedback_no_process_qualification',feedback=native['native_antenna_feedback_entries'],release_ready=False));return
        cases=[]
        def one(stage):
            case=output/('stage_'+str(stage))
            invoke(scripts[2],['--parent',parent,'--engine',engine,'--stage',str(stage),'--cpu',str(21+stage%2),'--output',case,'--paint-proof',output/'paint/assessment.json'],output/('stage_'+str(stage)+'.log'))
            return case
        for first in range(0,7,2):
            save(output/'status.json',dict(state='keeper_process_views_running',stages=list(range(first,min(first+2,7))),release_ready=False))
            with ThreadPoolExecutor(max_workers=2)as pool:cases.extend(pool.map(one,range(first,min(first+2,7))))
        args=[]
        for case in cases:args+=['--case',case]
        invoke(scripts[3],[*args,'--parent-geometry',output/'geometry/assessment.json','--paint-proof',output/'paint/assessment.json','--output',output/'process_audit'],output/'audit.log')
        verify(pins);receipts=[output/'geometry/assessment.json',output/'paint/assessment.json',output/'process_audit/assessment.json']
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in receipts},keeper_geometry_contact_and_process_checks_completed=True,
            exact_candidate_antenna_profile_qualified=False,parent_antenna_qualified=False,selected=False,release_ready=False))
        save(output/'status.json',dict(state='keeper_antenna_evidence_complete_profile_pending',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),original_parent_not_restarted=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.parent.resolve(),a.output.resolve())
