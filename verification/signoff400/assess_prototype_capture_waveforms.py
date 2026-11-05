"""Review capture waveforms, measured slew and all post-test output crossings."""
import argparse
import json
import math
from pathlib import Path
import re
import time
from common import save,sha,verify
from resources import lease
from assess_prototype_native_waveform import crossings


def table(text):
    rows=[]
    declared=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',text)
    if len(declared)!=1:raise ValueError('one transient data table required')
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].isdigit():continue
        if len(f)!=6:raise ValueError('time and four waveform columns required')
        index=int(f[0]);values=tuple(map(float,f[1:]))
        if index!=len(rows) or not all(math.isfinite(v) for v in values):raise ValueError('missing or malformed waveform row')
        if rows and values[0]<=rows[-1][0]:raise ValueError('nonmonotonic capture waveform')
        rows.append(values)
    if len(rows)!=int(declared[0]) or not rows or rows[0][0]!=0 or rows[-1][0]<30e-9-1e-18:
        raise ValueError('capture table truncated')
    return rows


def analyze(rows,case):
    def edges(column,threshold):return crossings([(r[0],r[column]) for r in rows],threshold)
    clock=edges(1,.9)[0]
    if len(clock)!=2 or any(abs(a-b*1e-9)>1e-12 for a,b in zip(clock,(10,20))):raise ValueError('unexpected clock waveform')
    column=3 if case['kind']=='async_release' else 2
    direction=1 if case['kind']=='data_fall' else 0
    changed=edges(column,.9)[direction]
    expected=(20+case['offset_ps']/1000)*1e-9
    if len(changed)!=1 or abs(changed[0]-expected)>1e-12:raise ValueError('unexpected data/control edge waveform')
    lo=edges(column,.36)[direction];hi=edges(column,1.44)[direction]
    if len(lo)!=1 or len(hi)!=1:raise ValueError('monotone test ramp required')
    qrise,qfall=edges(4,.9)
    after=18.5e-9
    events=sorted([(t,'rise') for t in qrise if t>=after]+[(t,'fall') for t in qfall if t>=after])
    correct_direction='rise' if case['kind']=='data_rise' or (case['kind']=='async_release' and case['pretest_expected']==0) else 'fall'
    delays=[(t-clock[1])*1e12 for t,d in events if d==correct_direction]
    if case['separated_control']:
        expected_edges=int(case['final_value']!=case['pretest_expected'])
        control_ok=case['separated_control_pass'] and len(events)==expected_edges and (not events or events[0][1]==correct_direction)
    else:control_ok=None
    return dict(kind=case['kind'],offset_ps=case['offset_ps'],outcome=case['outcome'],
        measured_input_minus_clock_ps=(changed[0]-clock[1])*1e12,
        measured_changing_input_slew_20_to_80_ps=abs(hi[0]-lo[0])*1e12,
        post_test_output_crossings=[dict(time_ns=t*1e9,direction=d,clock_relative_ps=(t-clock[1])*1e12) for t,d in events],
        signed_correct_direction_output_delays_ps=delays,
        output_crossing_count=len(events),separated_control_waveform_pass=control_ok)


def run(point,output):
    output.mkdir(parents=True,exist_ok=False)
    receipt=point/'assessment.json';r=json.loads(receipt.read_text())
    paths=[receipt,point/'observations.json',Path(__file__).resolve(),Path(__file__).with_name('assess_prototype_native_waveform.py')]
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        verify(r['input_sha256']);verify(r['artifacts'])
        if r['native_completed']!=21 or not r['separated_controls_pass']:raise ValueError('completed separated-control capture point required')
        observations=json.loads((point/'observations.json').read_text());records=[]
        for case in observations:
            if case['pretest_value']!=case['pretest_expected']:raise ValueError('invalid capture pretest state')
            file=point/f'{case["kind"]}_{case["offset_ps"]}ps/native.log';paths.append(file)
            records.append(analyze(table(file.read_text()),case))
        detail=output/'waveform_metrics.json';save(detail,records)
        save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(detail):sha(detail)},
            corner=r['corner'],master=r['master'],temperature_c=27,supply_v=1.8,
            waveforms=len(records),all_fixture_waveform_integrity_checks_pass=True,
            all_separated_control_output_crossings_pass=all(x['separated_control_waveform_pass'] for x in records if x['separated_control_waveform_pass'] is not None),
            input_full_ramp_ps=200,output_load_fF=20,setup_hold_recovery_removal_qualified=False,
            numerical_convergence_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Waveforms assessed:',len(records),'separated output crossing controls:',all(x['separated_control_waveform_pass'] for x in records if x['separated_control_waveform_pass'] is not None))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--point',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.point.resolve(),a.output.resolve())
