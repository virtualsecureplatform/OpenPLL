"""Review declared higher-load captures using measured slew and actual native load metadata."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
from pathlib import Path
import time
from common_v3 import PROFILE,save,sha,verify
from resources import identity
from assess_prototype_capture_waveforms_v2 import run as assess


def run(campaign,output):
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    save(output/'status.json',dict(state='waiting_for_native_load_campaign',release_ready=False))
    while not (campaign/'assessment.json').exists():
        owner=json.loads((campaign/'owner.json').read_text())
        if identity(owner['pid'])!=owner['birth']:raise ValueError('native campaign disappeared before terminal receipt')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('load review deadline')
        time.sleep(2)
    receipt=campaign/'assessment.json';manifest=campaign/'input_manifest.json'
    r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    declared=json.loads(manifest.read_text())['points']
    if len(declared)!=25 or len({(p['corner'],p['master']) for p in declared})!=25:raise ValueError('exact native coverage required')
    paths=[receipt,manifest,PROFILE,Path(__file__).resolve(),Path(__file__).with_name('assess_prototype_capture_waveforms_v2.py')]
    pins={str(p):sha(p) for p in paths}
    results=[];failures=[]
    def point(row):
        source=campaign/(row['corner']+'_'+row['master'].split('__')[1]);rp=source/'assessment.json'
        native=json.loads(rp.read_text())
        if (native['corner'],native['master'],native['output_load_fF'],native['input_slew_ps'])!=(row['corner'],row['master'],row['load_fF'],row['ramp_ps']):raise ValueError('declared/native point mismatch')
        dest=output/source.name;assess(source,dest)
        wp=dest/'assessment.json';wr=json.loads(wp.read_text())
        if wr['output_load_fF']!=row['load_fF'] or wr['input_full_ramp_ps']!=row['ramp_ps']:raise ValueError('review metadata mismatch')
        return dict(**row,assessment=str(wp),sha256=sha(wp),waveforms=wr['waveforms'],controls_pass=wr['all_separated_control_output_crossings_pass'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(point,row):row for row in declared}
        for future in as_completed(futures):
            try:results.append(future.result())
            except Exception as exc:failures.append(dict(point=futures[future],reason=repr(exc)))
            save(output/'status.json',dict(state='reviewing_native_load_campaign',reviewed_points=len(results),failed_points=len(failures),release_ready=False))
    verify(pins);detail=output/'points.json';save(detail,dict(results=results,failures=failures))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},reviewed_points=len(results),
        reviewed_waveforms=sum(p['waveforms'] for p in results),all_declared_waveforms_and_controls_pass=len(results)==25 and not failures and all(p['controls_pass'] for p in results),
        native_load_and_slew_metadata_verified=True,measured_input_slew_verified=True,
        legacy_reviewer_fixed_20fF_metadata_superseded=True,receiver_pin_and_parent_load_bound_proven=False,
        setup_hold_recovery_removal_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='capture_load_waveform_review_terminal',reviewed_points=len(results),failed_points=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.campaign.resolve(),a.output.resolve())
