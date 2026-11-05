"""Measure reset-zero event-toggle publication delays by role and Q direction.

Observed intervals are diagnostic samples, not uniform timing/uncertainty bounds.
Incomplete direction coverage remains explicit; no missing delay is filled.
"""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources
from assess_selected_detector_prefix import read_prefix
from assess_selected_detector_phase_probe_v4 import transitions


def merge(pins,other):
    for path,digest in other.items():
        if path in pins and pins[path]!=digest:raise ValueError('conflicting native input identity')
        pins[path]=digest


def measure(case,inventory):
    status=json.loads((case/'status.json').read_text())['state']
    if status not in ['nearzero_conditional_response_measured','recorded_phase_response_measured','corner_detector_response_measured']:raise ValueError('completed original native case required')
    native=case/'native';manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    a_path=case/'waveform_assessment/assessment.json';a=json.loads(a_path.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if a['input_sha256'].get(str(manifest))!=sha(manifest):raise ValueError('native observation provenance mismatch')
    iv=json.loads(inventory.read_text());verify(iv['input_sha256'])
    lib=re.findall(r'^\.lib\s+"([^"]+)"\s+(tt|ff|ss|sf|fs)$',(native/'probe.spice').read_text(),re.MULTILINE)
    if len(lib)!=1 or '.options device temp=27' not in (native/'probe.spice').read_text().splitlines():raise ValueError('declared PDK corner and temperature required')
    vs=sources(native/'sources.spice')
    if any(float(vs[node][1])!=voltage for node,voltage in [('VPWR',1.8),('VPB',1.8),('VGND',0),('VNB',0)]):raise ValueError('nominal physical supplies required')
    op=dict(corner=lib[0][1],temperature_c=27,supply_v=1.8)
    if m.get('operating_point',op)!=op:raise ValueError('native corner metadata/deck mismatch')
    models={p:d for p,d in m['input_sha256'].items() if p.endswith('/model.spice')}
    if len(models)!=1:raise ValueError('unique assembled native model required')
    rows,info=read_prefix(native/'probe.raw',m['observed_roles']);roles=list(m['observed_roles']);duration=a.get('native_duration_ns',80)
    if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-duration*1e-9)>1e-18:raise ValueError('complete finite native observation required')
    if any(row[roles.index('detector_up')+1]>=.9 and row[roles.index('detector_dn')+1]>=.9 for row in rows):raise ValueError('overlapping BBPD channels outside this publication protocol')
    records=[]
    for role,port in [('up','BBPD[1]'),('dn','BBPD[0]')]:
        key=iv['roles'][port]['event_clock_receiver'];cell=next(c for c in iv['selected_cells'] if c['cell_key']==key)
        matches=[r for r,node in m['observed_roles'].items() if node==cell['pins']['Q']]
        if len(matches)!=1:raise ValueError('unique native event-toggle Q required')
        column=roles.index(matches[0])+1
        if rows[0][column]>=.18:raise ValueError('native reset-zero publication state required')
        clock=transitions(rows,roles.index('detector_'+role)+1)['rising_ns'];qe=transitions(rows,column)
        output=sorted([(t,'rise') for t in qe['rising_ns']]+[(t,'fall') for t in qe['falling_ns']])
        if len(clock)!=len(output):raise ValueError('one native event publication per detector rise required')
        for i,(ct,(qt,edge)) in enumerate(zip(clock,output)):
            stop=clock[i+1] if i+1<len(clock) else duration
            if edge!=('rise' if i%2==0 else 'fall') or not ct<qt<stop:raise ValueError('causal alternating reset-zero event publications required')
            records.append(dict(role=role,Q_edge=edge,detector_rise_ns=ct,event_Q_ns=qt,latency_ns=qt-ct))
    if not records:raise ValueError('active publication observations required')
    pins={str(p):sha(p) for p in [manifest,a_path,native/'probe.raw',inventory]}
    return dict(case=str(case),operating_point=op,native_model_sha256=models,records=records),pins


def parameters(records):
    result={role:{} for role in ['up','dn']}
    for role in result:
        for edge in ['rise','fall']:
            values=[r['latency_ns'] for r in records if r['role']==role and r['Q_edge']==edge]
            if values:result[role][edge]=dict(observed_interval_ns=[min(values),max(values)],nominal_ns=(min(values)+max(values))/2,samples=len(values))
    return result


def run(cases,inventory,output):
    if not cases or len(set(cases))!=len(cases):raise ValueError('distinct native training cases required')
    output.mkdir(parents=True,exist_ok=False);measured=[];pins={}
    for case in cases:
        observation,inputs=measure(case,inventory);measured.append(observation);merge(pins,inputs)
    identity=[(r['operating_point'],r['native_model_sha256']) for r in measured]
    if any(p!=identity[0] for p in identity):raise ValueError('publication training must share physical model and operating point')
    records=[dict(case=r['case'],**entry) for r in measured for entry in r['records']];p=parameters(records)
    files=[Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v4.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]
    merge(pins,{str(path):sha(path) for path in files});verify(pins)
    missing=[dict(role=role,Q_edge=edge) for role in ['up','dn'] for edge in ['rise','fall'] if edge not in p[role]]
    save(output/'parameters.json',dict(operating_point=identity[0][0],native_model_sha256=identity[0][1],training_cases=list(map(str,cases)),publication_delays=p,missing_directions=missing,reset_Q=0,uniform_uncertainty_bound_qualified=False,release_ready=False))
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'parameters.json'):sha(output/'parameters.json')},records=records,missing_directions=missing,direction_coverage_complete=not missing,observed_intervals_only=True,independent_holdouts_complete=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(publication_delays=p,missing_directions=missing)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',type=Path,action='append',required=True)
    for name in ['inventory','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run([p.resolve() for p in args.case],args.inventory.resolve(),args.output.resolve())
