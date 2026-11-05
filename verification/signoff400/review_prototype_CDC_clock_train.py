"""Aggregate native rail observations made before the next clock-train edge."""
import argparse
import json
import math
from pathlib import Path
from common_v3 import save,sha,verify

def run(campaign,output):
    receipt=campaign/'assessment.json';authority=json.loads(receipt.read_text());verify(authority['artifacts'])
    if authority.get('clock_period_ns')!=2 or authority.get('clock_high_ns')!=1 or authority.get('native_points_completed')!=45:
        raise ValueError('complete declared clock-train campaign required')
    pins={str(p):sha(p) for p in (receipt,Path(__file__).resolve())}
    points=[];keys=set();maxima={};unresolved=0
    for name,digest in authority['input_sha256'].items():
        path=Path(name)
        if path.name!='assessment.json' or not (path.parent/'observations.json').exists():continue
        record=json.loads(path.read_text())
        if record.get('clock_period_ns')!=2:continue
        if sha(path)!=digest:raise ValueError('native point authority changed')
        verify(record['input_sha256']);verify(record['artifacts'])
        if not record['all_pretest_states_verified'] or record['master']!='sky130_fd_sc_hs__dfrtp_1' or record['load_fF']!=20 or record['clock_high_ns']!=1:
            raise ValueError('native first-stage fixture identity or initialization differs')
        key=(record['corner'],record['input_full_ramp_ps'],record['clock_full_ramp_ps'])
        if key in keys:raise ValueError('duplicate electrical corner')
        keys.add(key)
        detail=path.parent/'observations.json';rows=json.loads(detail.read_text())
        offsets=(-1500,-1000,-750,-500,-400,-300,-200,-150,-100,-75,-50,-25,0,25,50,75,100,150,200,300,400,500,750,1000,1500)
        expected_cases={(kind,offset) for kind in ('data_rise','data_fall','async_release') for offset in offsets}
        if len(rows)!=75 or {(r['kind'],r['offset_ps']) for r in rows}!=expected_cases:
            raise ValueError('complete distinct 75-case native point required')
        tails=[];missing=0
        for row in rows:
            metrics=row['waveform_metrics']
            if metrics['observation_end_ns']!=21.8 or metrics['next_clock_rising_ns']!=22 or not metrics['next_clock_cannot_mask_observed_resolution']:
                raise ValueError('observation must end before next clock')
            tail=metrics['observed_resolution_ns_from_test_edge'];rail=metrics['observed_pre_next_edge_rail']
            if rail is None:
                if tail is not None:raise ValueError('unresolved rail has no finite bound')
                missing+=1
            else:
                if rail not in (0,1) or tail is None or not math.isfinite(tail) or not 0<=tail<1.81:
                    raise ValueError('invalid pre-next-edge rail observation')
                tails.append(tail)
        corner=key[0];unresolved+=missing
        if tails:maxima[corner]=max(maxima.get(corner,0),max(tails))
        points.append(dict(point=str(path.parent),corner=corner,input_full_ramp_ps=key[1],clock_full_ramp_ps=key[2],unresolved_cases=missing,maximum_observed_resolution_ns=max(tails) if tails else None))
        pins.update({str(p):sha(p) for p in (path,detail)})
    expected={(c,d,k) for c in ('tt','ff','ss','sf','fs') for d in (20,200,2000) for k in (20,200,400)}
    if keys!=expected:raise ValueError('five-corner slew rectangle incomplete')
    verify(pins);output.mkdir(parents=True,exist_ok=False);report=output/'observations.json';save(report,points)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},
         native_points_reviewed=45,native_cases_reviewed=3375,clock_period_ns=2,clock_high_ns=1,
         observation_end_ns=21.8,next_clock_edge_ns=22,observed_maximum_resolution_ns_by_corner=maxima,
         unresolved_final_rail_cases=unresolved,old_or_new_final_state_both_allowed=True,
         clock_train_applied=True,all_clock_periods_or_duty_cycles_qualified=False,
         statistical_or_continuous_metastability_bound_proved=False,FIT_qualified=False,
         actual_routed_resolution_budget_compared=False,physical_CDC_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.campaign.resolve(),args.output.resolve())
