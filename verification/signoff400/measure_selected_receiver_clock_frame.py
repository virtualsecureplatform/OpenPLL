"""Measure a receiver's recorded clock frame relative to PLLOUT; no timing qualification."""
import argparse,bisect,csv,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from selected_native_clock_shapes import load,shift_window
from assess_selected_detector_phase_probe_v4 import transitions


def pair(root,local,limit_ns=1):
    pairs=[]
    for i,t in enumerate(local):
        j=bisect.bisect_right(root,t)-1
        if j<0 or t-root[j]>limit_ns:raise ValueError('no preceding root edge within declared pairing interval')
        if pairs and j<=pairs[-1]['root_index']:raise ValueError('root edge reused or out of order')
        pairs.append(dict(local_index=i,root_index=j,root_ns=root[j],local_ns=t,transport_ps=(t-root[j])*1000))
    return pairs


def run(case,replay,reference,model,output):
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    provenance=reference/'provenance.json';p=json.loads(provenance.read_text());verify(p['artifacts'])
    if not p['original_CSV_reproduced_byte_for_byte']:raise ValueError('native CSV provenance required')
    signals=reference/'signals.csv'
    if p['artifacts'].get(str(signals))!=sha(signals):raise ValueError('CSV not bound by reference provenance')
    shape=case/'native/native_shape_construction.json';s=json.loads(shape.read_text());verify(s['input_sha256'])
    assessment=replay/'assessment.json';a=json.loads(assessment.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a.get('selected_physical_RTL_receiver_replayed'):raise ValueError('selected-layout receiver replay required')
    shifts=[s['clock_sources'][k]['time_translation_s'] for k in ['synchronizer_clock','second_synchronizer_clock']]
    if shifts[0]!=shifts[1]:raise ValueError('common receiver clock translation required')
    root=[]
    with signals.open() as stream:
        for row in csv.DictReader(stream):
            t,v=float(row['time']),float(row['v(pllout)'])
            if not math.isfinite(t) or not math.isfinite(v):raise ValueError('finite root waveform required')
            root.append((t,v))
    root=shift_window(root,shifts[0],80e-9)
    rising=lambda rows:transitions(rows,1)['rising_ns']
    root_edges=rising(root);clocks={};files=[provenance,signals,shape,assessment,Path(__file__).resolve()]
    for role,key in [('first','synchronizer_clock'),('second','second_synchronizer_clock')]:
        source=case/'native/bounded_clock_sources'/(key+'_bounded.pwl');files.append(source)
        if a['input_sha256'].get(str(source))!=sha(source):raise ValueError('receiver source not bound by replay')
        edges=rising(load(source));clocks[role]=pair(root_edges,edges)
    receipt=model/'assessment.json';params=model/'parameters.json';m=json.loads(receipt.read_text());verify(m['input_sha256']);verify(m['artifacts']);files += [receipt,params]
    if a['publication_model']!=str(model):raise ValueError('same independently fitted publication model required')
    publication=json.loads(params.read_text())['publication_delays']
    records=[]
    for role in ['up','dn']:
        first=next(r for r in a['records'] if r['role']==role)
        second=next(r for r in a['second_stage_records'] if r['role']==role)
        for f,n in zip(first['samples'],second['samples']):
            x=clocks['first'][f['native_sampling_clock_index']];y=clocks['second'][n['native_sampling_clock_index']]
            records.append(dict(role=role,first_root_index=x['root_index'],second_root_index=y['root_index'],root_cycle_separation=y['root_index']-x['root_index'],first_to_second_data_transport_ps=(n['native_data_ns']-f['native_first_stage_ns'])*1000,second_data_lead_ps=n['native_data_lead_ps'],paired_clock_skew_ps=y['transport_ps']-x['transport_ps']))
    save(output/'assessment.json',dict(input_sha256={str(f):sha(f) for f in files},clock_pairs=clocks,records=records,publication_model_delays=publication,root_clock_node='PLLOUT',common_time_translation_s=shifts[0],pairing_limit_ns=1,scope='recorded TT receiver clock frame and sampled interstage transfer; nearest preceding root edges only',unwrapped_causal_latency_qualified=False,uniform_uncertainty_bound_qualified=False,complete_controller_timing_qualified=False,release_ready=False))
    print(json.dumps(dict(clock_transport_ps={k:[min(x['transport_ps'] for x in v),max(x['transport_ps'] for x in v)] for k,v in clocks.items()},records=records)))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['case','replay','reference','model','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['case','replay','reference','model','output']))
