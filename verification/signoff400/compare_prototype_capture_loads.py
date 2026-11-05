"""Compare matched native capture observations at two declared output loads; qualify no tables."""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify


def transitions(rows):
    selected=sorted(rows,key=lambda r:r['offset_ps'])
    offsets=[r['offset_ps'] for r in selected]
    if offsets!=[-1000,-500,-200,0,200,500,1000]:raise ValueError('exact declared offset coverage required')
    outcomes=[r['outcome'] for r in selected]
    changed=[r['offset_ps'] for r in selected if r['outcome']=='changed_value']
    old=[r['offset_ps'] for r in selected if r['outcome']=='pretest_value']
    monotone=all(x in ('changed_value','pretest_value') for x in outcomes) and bool(changed and old) and max(changed)<min(old)
    return dict(offsets_ps=offsets,outcomes=outcomes,observed_single_transition=monotone,
        observed_transition_bracket_ps=[max(changed),min(old)] if monotone else None,
        setup_hold_recovery_removal_qualified=False)


def run(low,high,output):
    output.mkdir(parents=True,exist_ok=False)
    receipts=[p/'assessment.json' for p in (low,high)]
    reports=[json.loads(p.read_text()) for p in receipts]
    pins={str(p):sha(p) for p in [*receipts,Path(__file__).resolve()]}
    data=[]
    for directory,r in zip((low,high),reports):
        verify(r['input_sha256']);verify(r['artifacts'])
        if r['waveforms']!=21 or not r['all_separated_control_output_crossings_pass']:raise ValueError('complete native waveform review required')
        metric=directory/'waveform_metrics.json'
        if r['artifacts'].get(str(metric))!=sha(metric):raise ValueError('waveform metrics not pinned')
        pins[str(metric)]=sha(metric);rows=json.loads(metric.read_text())
        if len(rows)!=21 or len({(x['kind'],x['offset_ps']) for x in rows})!=21:raise ValueError('duplicate/missing waveform cases')
        data.append(rows)
    for key in ('corner','master','temperature_c','supply_v','input_full_ramp_ps'):
        if reports[0][key]!=reports[1][key]:raise ValueError('unmatched observation parameter: '+key)
    if not 0<reports[0]['output_load_fF']<reports[1]['output_load_fF']:raise ValueError('strictly increasing declared loads required')
    # Follow each reviewed native receipt to its isolated cell model and simulator.
    # Same master label alone is insufficient to establish model identity.
    models=[];binaries=[]
    for r in reports:
        native_receipts=[Path(p) for p in r['input_sha256'] if Path(p).name=='assessment.json']
        if len(native_receipts)!=1:raise ValueError('one reviewed native receipt required')
        nr=native_receipts[0];native=json.loads(nr.read_text());verify(native['input_sha256']);verify(native['artifacts']);pins[str(nr)]=sha(nr)
        model=[v for p,v in native['input_sha256'].items() if Path(p).name=='cell.spice']
        ng=[v for p,v in native['input_sha256'].items() if Path(p).name=='ngspice']
        if len(model)!=1 or len(ng)!=1:raise ValueError('unique native model and simulator required')
        models.append(model[0]);binaries.append(ng[0])
    if len(set(models))!=1 or len(set(binaries))!=1:raise ValueError('native model or simulator differs')
    results={}
    for kind in ('data_rise','data_fall','async_release'):
        a,b=[[r for r in rows if r['kind']==kind] for rows in data]
        controls=[]
        for rows in (a,b):
            row=next(r for r in rows if r['offset_ps']==-1000)
            delays=row['signed_correct_direction_output_delays_ps']
            if not row['separated_control_waveform_pass'] or len(delays)!=1:raise ValueError('one clean separated-control output crossing required')
            controls.append(delays[0])
        results[kind]=dict(low_load=transitions(a),high_load=transitions(b),
            separated_control_clock_to_Q_ps=controls,observed_clock_to_Q_change_ps=controls[1]-controls[0])
    detail=output/'comparison.json';save(detail,results);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        corner=reports[0]['corner'],master=reports[0]['master'],load_pair_fF=[r['output_load_fF'] for r in reports],
        full_input_ramp_ps=reports[0]['input_full_ramp_ps'],native_model_and_simulator_identity_match=True,
        receiver_pin_and_parent_load_bound_proven=False,intermediate_load_interpolation_qualified=False,
        setup_hold_recovery_removal_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('low','high','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.low.resolve(),a.high.resolve(),a.output.resolve())
