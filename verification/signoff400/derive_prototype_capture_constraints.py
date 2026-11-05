"""Derive conservative sampled capture constraints; routed timing qualification remains separate."""
import argparse
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify
from audit_prototype_final_campaign_coverage_v3 import merge_pins, CORNERS, MASTERS, LOADS


def bounds(point,kind,margin):
    row=next(x for x in point['observed_brackets'] if x['kind']==kind)
    before=row['latest_sampled_clean_before_ps'];after=row['earliest_sampled_clean_after_ps']
    if before is None or after is None or not before<0<after:
        raise ValueError('both sides of the sampled capture aperture must be bracketed')
    return -before+margin,after+margin


def run(expanded,fast,numerical,pulse,margin,output):
    if not math.isfinite(margin) or margin<5:raise ValueError('engineering allowance must cover the baseline 5 ps step')
    receipts=[p/'assessment.json' for p in (expanded,fast,numerical,pulse)]
    a,b,n,p=[json.loads(f.read_text()) for f in receipts]
    if (a.get('exact_native_case_coverage_verified'),a.get('native_cases'),b.get('exact_native_case_coverage_verified'),b.get('native_cases'))!=(True,3000,True,3750):
        raise ValueError('audited complete capture meshes required')
    if not n['all_sampled_outcomes_and_crossing_counts_match'] or n['compared_native_case_pairs']!=600:
        raise ValueError('matching tighter numerical holdouts required')
    if margin<2*n['maximum_paired_edge_displacement_ps']:raise ValueError('allowance smaller than twice observed numerical shift')
    if not p['all_pretest_states_verified'] or not p['all_actual_clock_edges_slews_and_loads_verified'] or p['native_cases']!=400:
        raise ValueError('complete independent pulse waveform review required')
    pins={str(f):sha(f) for f in (*receipts,Path(__file__).resolve(),
          Path(__file__).with_name('audit_prototype_final_campaign_coverage_v3.py'))}
    for record in (a,b,n,p):merge_pins(pins,record)
    grids={};models={m:set() for m in MASTERS}
    for campaign in (expanded,fast):
        source=campaign/'points.json';pins[str(source)]=sha(source)
        for row in json.loads(source.read_text()):
            directory=Path(row['directory']);native=directory/'assessment.json'
            r=json.loads(native.read_text());merge_pins(pins,r)
            if r['load_fF']!=LOADS[row['master']]:raise ValueError('capture load point differs')
            cells=[h for f,h in r['input_sha256'].items() if f.endswith('/cell.spice')]
            if len(cells)!=1:raise ValueError('unique final native cell model required')
            models[row['master']].add(cells[0])
            review=directory.parent/(directory.name+'_review');receipt=review/'assessment.json'
            rr=json.loads(receipt.read_text());merge_pins(pins,rr)
            if rr['input_sha256'].get(str(native))!=sha(native):raise ValueError('capture review lineage differs')
            detail=review/'observations.json';point=json.loads(detail.read_text())
            key=(point['corner'],point['master'].removeprefix('sky130_fd_sc_hs__'),point['input_full_ramp_ps'],point['clock_full_ramp_ps'])
            if key in grids:raise ValueError('duplicate native capture grid')
            grids[key]=point;pins[str(detail)]=sha(detail)
    expected={(c,m,d,k) for c in CORNERS for m in MASTERS for d in (20,200,2000) for k in (20,200,400)}
    if grids.keys()!=expected or any(len(v)!=1 for v in models.values()):raise ValueError('complete same-model five-corner capture mesh required')
    pulse_file=pulse/'observations.json';pulse_rows=json.loads(pulse_file.read_text());pins[str(pulse_file)]=sha(pulse_file)
    pulses={}
    for row in pulse_rows:
        key=(row['corner'],row['master'].removeprefix('sky130_fd_sc_hs__'),row['clock_full_ramp_ps'])
        if key in pulses:raise ValueError('duplicate pulse grid')
        pulses[key]=row
    if pulses.keys()!={(c,m,k) for c in CORNERS for m in MASTERS for k in (20,400)}:
        raise ValueError('complete pulse endpoint coverage required')
    result=[]
    for c in CORNERS:
        for m in MASTERS:
            tables={}
            for kind,before_name,after_name in (('data_rise','setup_rise_ps','hold_rise_ps'),
                    ('data_fall','setup_fall_ps','hold_fall_ps'),('async_release','recovery_rise_ps','removal_rise_ps')):
                before=[];after=[]
                for d in (20,200,2000):
                    paired=[bounds(grids[c,m,d,k],kind,margin) for k in (20,200,400)]
                    before.append([x[0] for x in paired]);after.append([x[1] for x in paired])
                tables[before_name]=before;tables[after_name]=after
            widths={}
            for kind in ('high','low'):
                tested=[pulses[c,m,k]['sampled_thresholds'][kind]['smallest_tested_width_with_all_larger_samples_passing_ps'] for k in (20,400)]
                if None in tested:raise ValueError('no passing clock pulse bound at a measured slew endpoint')
                widths[kind]=max(tested)+margin
            result.append(dict(corner=c,master='sky130_fd_sc_hs__'+m,load_fF=LOADS[m],
                 native_cell_model_sha256=next(iter(models[m])),input_slew_20_to_80_ps=[12,120,1200],
                 related_clock_slew_20_to_80_ps=[12,120,240],tables=tables,
                 minimum_tested_clock_pulse_allowance_ps=widths,engineering_margin_ps=margin,
                 margin_is_not_a_universal_numerical_error_bound=True))
    verify(pins);output.mkdir(parents=True,exist_ok=False);detail=output/'constraints.json';save(detail,result)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         native_capture_cases=6750,native_capture_grids=225,master_corner_constraint_sets=25,
         engineering_margin_ps=margin,all_capture_apertures_bracketed=True,
         complete_same_model_data_and_clock_slew_mesh_verified=True,
         interpolation_between_sampled_apertures_qualified=False,actual_routed_load_and_slew_enclosure_qualified=False,
         native_capture_constraints_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('expanded','fast','numerical','pulse','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--engineering-margin-ps',type=float,default=10)
    a=p.parse_args();run(a.expanded.resolve(),a.fast.resolve(),a.numerical.resolve(),a.pulse.resolve(),
                        a.engineering_margin_ps,a.output.resolve())
