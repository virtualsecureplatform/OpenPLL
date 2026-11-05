"""Replay native decision-path captures under the explicitly proved enabled phase contract."""
import argparse,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from assess_prototype_native_waveform import crossings


def review(rows):
    if not rows or rows[0][0]!=0 or rows[-1][0]<64e-9-1e-15:raise ValueError('complete native waveform required')
    def events(column):
        rise,fall=crossings([(r[0],r[column]) for r in rows],.9)
        return sorted([(t,'rise') for t in rise if t>2e-9]+[(t,'fall') for t in fall if t>2e-9])
    data=events(6);capture=[t for t,d in events(5) if d=='rise'];outputs=events(7);source=events(4)
    if len(data)!=2 or len(source)!=2 or len(capture)!=2 or len(outputs)!=2:
        raise ValueError('two legal updates and two native captures required')
    if [d for t,d in data]!=['rise','fall'] or [d for t,d in source]!=['rise','fall'] or [d for t,d in outputs]!=['rise','fall']:
        raise ValueError('native data/output directions differ')
    records=[]
    for i,t in enumerate(capture):
        previous=[x for x,d in data if x<t];following=[x for x,d in data if x>t]
        if not previous:raise ValueError('no native data transition preceding capture')
        expected=1.8 if i==0 else 0
        sample=[r[7] for r in rows if t+1e-9<=r[0]<=t+2e-9]
        if not sample:raise ValueError('native postcapture interval absent')
        valid=min(sample)>1.62 if expected else max(sample)<.18
        delay=outputs[i][0]-t
        if not valid or not 0<delay<1e-9:raise ValueError('native capture differs from stable source data')
        records.append(dict(clock_time_ns=t*1e9,expected_value=int(bool(expected)),
            D_stable_before_clock_ns=(t-max(previous))*1e9,
            D_stable_after_clock_to_next_transition_or_end_ns=((min(following) if following else rows[-1][0])-t)*1e9,
            clock_to_Q_ns=delay*1e9,postcapture_voltage_interval_v=[min(sample),max(sample)]))
    return dict(captures=records,source_Q_to_destination_D_delay_ns=[(d[0]-s[0])*1e9 for s,d in zip(source,data)])


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    if not r['native_path_waveform_complete']:raise ValueError('completed native path required')
    wave=source/'wave.prn';data=[];terminal=False
    with wave.open() as stream:
        stream.readline()
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:terminal=True;continue
            f=line.split()
            if not f:continue
            if terminal or len(f)!=9 or int(f[0])!=len(data):raise ValueError('native waveform row differs')
            row=list(map(float,f[1:]))
            if not all(map(math.isfinite,row)) or (data and row[0]<=data[-1][0]):raise ValueError('nonfinite or nonmonotonic native path')
            data.append(row)
    if not terminal:raise ValueError('native waveform terminal marker absent')
    metrics=review(data);paths=[receipt,wave,source/'plan.json',Path(__file__).resolve(),Path(__file__).with_name('assess_prototype_native_waveform.py')]
    pins={str(p):sha(p) for p in paths};verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'captures.json';save(detail,metrics)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},corner=r['corner'],
        both_declared_native_captures_match=True,all_native_data_and_output_transitions_accounted_for=True,
        generated_clock_source_latency_included=False,other_reachable_update_phases_covered=False,
        enable_withdrawal_and_reset_scenarios_covered=False,numerical_uncertainty_included=False,
        native_path_correlation_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
