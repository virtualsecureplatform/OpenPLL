"""Review all 525 native capture waveforms with explicit master/corner coverage."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
from common_v3 import PROFILE,save,sha,verify,spec
from assess_prototype_capture_waveforms import run as assess


def run(campaign,output):
    output.mkdir(parents=True,exist_ok=False)
    receipt=campaign/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['all_25_nominal_capture_points_complete']:raise ValueError('completed capture campaign required')
    points=campaign/'points.json';p=json.loads(points.read_text());rows=p['results']
    masters={'sky130_fd_sc_hs__dfrtp_1','sky130_fd_sc_hs__dfrtp_2','sky130_fd_sc_hs__dfrtp_4','sky130_fd_sc_hs__dfstp_1','sky130_fd_sc_hs__dfstp_4'}
    expected={(c,m) for c in spec()['corners'] for m in masters}
    if len(rows)!=25 or {(x['corner'],x['master']) for x in rows}!=expected:raise ValueError('exact 25-point coverage required')
    pins={str(f):sha(f) for f in (receipt,points,PROFILE,Path(__file__).resolve(),Path(__file__).with_name('assess_prototype_capture_waveforms.py'))}
    for row in rows:
        if sha(Path(row['assessment']))!=row['assessment_sha256']:raise ValueError('capture point receipt changed')
    results=[];failures=[]
    def point(row):
        directory=output/(row['corner']+'_'+row['master'].rsplit('__',1)[1])
        assess(Path(row['assessment']).parent,directory)
        rp=directory/'assessment.json';report=json.loads(rp.read_text())
        return dict(corner=row['corner'],master=row['master'],assessment=str(rp),sha256=sha(rp),
                    waveforms=report['waveforms'],controls_pass=report['all_separated_control_output_crossings_pass'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(point,row):(row['corner'],row['master']) for row in rows}
        for future in as_completed(futures):
            try:results.append(future.result())
            except Exception as error:failures.append(dict(point=list(futures[future]),reason=repr(error)))
            save(output/'status.json',dict(state='capture_waveform_campaign_review_running',reviewed_points=len(results),failed_points=len(failures),release_ready=False))
    detail=output/'points.json';save(detail,dict(results=results,failures=failures));verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         exact_master_corner_coverage_verified=True,reviewed_points=len(results),reviewed_waveforms=sum(x['waveforms'] for x in results),
         all_525_waveforms_and_controls_pass=len(results)==25 and not failures and all(x['controls_pass'] for x in results),
         input_full_ramp_ps=200,nominal_linear_slew_20_to_80_ps=120,output_load_fF=20,
         setup_hold_recovery_removal_qualified=False,other_load_slew_points_covered=False,
         diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='capture_waveform_campaign_review_terminal',reviewed_points=len(results),failed_points=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.campaign.resolve(),a.output.resolve())
