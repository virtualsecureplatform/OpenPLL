"""Measure native variation omitted by constant reduced-DCO exterior cuts.

Capacitance-weighted variation ranks missing voltage forcing; it is not a
frequency-error bound, a causal attribution, or physical-model qualification.
"""
import argparse,csv,json,math,os,subprocess,time
from collections import defaultdict
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from capture_selected_native_initial_snapshot import fingerprint
from check_selected_boundary_waveforms import bind
from audit_selected_dco_history_inputs import sources


def run(reference,native,snapshot,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='measuring_native_boundary_variation',release_ready=False))
    try:
        receipt=snapshot/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
        raw=native/'profile.raw';manifest=native/'manifest.json'
        if fingerprint(raw)!=r['source_file_fingerprint'] or r['input_sha256'].get(str(manifest))!=sha(manifest):raise ValueError('verified original native RAW identity required')
        m=json.loads((reference/'manifest.json').read_text());verify({p:d for p,d in m['input_sha256'].items() if p!=str(raw)})
        vector=json.loads((snapshot/'initial_voltage_vector.json').read_text());names=vector['variable_names']
        fixed={}
        for node,(name,value) in sources(reference/'sources.spice').items():
            if node in ['0','VPWR','VGND','VPB','VNB']:continue
            try:v=float(value)
            except ValueError:continue
            if not math.isfinite(v):raise ValueError('finite constant source required')
            fixed[node]=v
        binding=bind(list(fixed),names)
        if not binding['all_bound']:raise ValueError('all quiet exterior nodes must have actual native voltage observations')
        weights=defaultdict(float);rails={'0','VPWR','VGND','VPB','VNB'}
        for line in (reference/'devices.spice').open():
            f=line.split()
            if len(f)!=4 or not f[0].lower().startswith('c'):continue
            try:c=abs(float(f[3]))
            except ValueError:raise ValueError('literal capacitor required')
            if not math.isfinite(c):raise ValueError('finite capacitor required')
            for node,other in [(f[1],f[2]),(f[2],f[1])]:
                if node in fixed and other not in fixed and other not in rails:weights[node]+=c
        indices=output/'indices.txt';indices.write_text(''.join(str(binding['bindings'][n]['index'])+'\n' for n in fixed))
        source=ROOT/'tools/xyce_waveform/boundary_window_statistics.cpp';binary=output/'statistics';table=output/'statistics.csv'
        paths=[reference/'manifest.json',reference/'sources.spice',reference/'devices.spice',manifest,receipt,snapshot/'initial_voltage_vector.json',source,Path(__file__).resolve(),indices,
               Path(__file__).with_name('capture_selected_native_initial_snapshot.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('check_selected_boundary_waveforms.py')]
        pins={str(p):sha(p) for p in paths};verify(pins)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        with lease(1,2,deadline):
            subprocess.run(['g++','-O3','-std=c++17',source,'-o',binary],check=True,timeout=120)
            pins[str(binary)]=sha(binary)
            execute([binary,raw,indices,table,'2e-7','2.6e-7'],output/'extraction.log',deadline,2)
        if fingerprint(raw)!=r['source_file_fingerprint']:raise ValueError('native RAW changed during observation')
        verify(pins);pins[str(raw)]=r['input_sha256'][str(raw)]
        with table.open() as stream:rows=list(csv.DictReader(stream))
        if len(rows)!=len(fixed):raise ValueError('complete boundary statistics required')
        records=[]
        for (node,held),row in zip(fixed.items(),rows):
            if int(row['index'])!=binding['bindings'][node]['index']:raise ValueError('native boundary column identity mismatch')
            lo,hi,tv,last,mean=[float(row[k]) for k in ['minimum_V','maximum_V','total_variation_V','last_V','time_mean_V']]
            records.append(dict(node=node,held_V=held,minimum_V=lo,maximum_V=hi,last_V=last,time_mean_V=mean,
                span_V=hi-lo,total_variation_V=tv,absolute_C_to_retained_nongrounded_nodes_F=weights[node],
                capacitance_weighted_variation_C=weights[node]*tv,held_vs_final_native_V=held-last))
        records.sort(key=lambda x:x['capacitance_weighted_variation_C'],reverse=True);save(output/'boundaries.json',records)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [table,output/'boundaries.json',output/'extraction.log']},
            measurement_window_ns=[200,260],constant_boundary_nodes=len(records),
            nodes_with_span_above_0p1V=sum(x['span_V']>.1 for x in records),
            max_held_vs_final_native_V=max(abs(x['held_vs_final_native_V']) for x in records),
            top_capacitance_weighted_variation=records[:20],
            ranking_scope='absolute literal C to retained nongrounded nodes times native total voltage variation; no frequency bound',
            full_boundary_forcing_replayed=False,frequency_error_causality_demonstrated=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='native_boundary_variation_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','native','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','native','snapshot','output']))
