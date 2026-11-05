"""Compare isolated DCO bias sources with the full native final voltage vector.

A verified full-RAW fingerprint permits a bounded tail read. This checks the
final logical biases, not transient programming, source impedance, load
correlation, oscillator settling, or physical model qualification.
"""
import argparse,json,math,re
from pathlib import Path
from common_v3 import save,sha,verify
from capture_selected_native_initial_snapshot import fingerprint
from check_selected_boundary_waveforms import bind
from compare_prototype_physical_primitive_graphs import parsed


def last_sample(raw,expected):
    if fingerprint(raw)!=expected:raise ValueError('RAW differs from verified snapshot fingerprint')
    names=[];variables=None;points=None
    with raw.open() as f:
        for line in f:
            if line.startswith('No. Variables:'):variables=int(line.split(':',1)[1])
            if line.startswith('No. Points:'):points=int(line.split(':',1)[1])
            if line.strip()=='Variables:':break
        for line in f:
            if line.strip()=='Values:':break
            index,name,_=line.split()
            if int(index)!=len(names):raise ValueError('invalid native variable ordering')
            names.append(name)
    if variables!=len(names) or not points or names[0].lower()!='time':raise ValueError('complete native header required')
    with raw.open('rb') as f:
        f.seek(max(0,expected[2]-2*1024*1024));lines=f.read().decode().splitlines()
    markers=[]
    for i,line in enumerate(lines):
        fields=line.split()
        if len(fields)==2 and fields[0].isdigit() and int(fields[0])==points-1:markers.append((i,float(fields[1])))
    if len(markers)!=1:raise ValueError('one final complete native sample required')
    index,t=markers[0];values=[t]+[float(line) for line in lines[index+1:] if line.strip()]
    if len(values)!=variables or not all(math.isfinite(v) for v in values) or abs(t-260e-9)>1e-18:raise ValueError('incomplete finite final 260 ns vector')
    if fingerprint(raw)!=expected:raise ValueError('native RAW changed during tail read')
    return names,values


def run(hierarchy,metadata,wire_map,isolated_deck,raw,snapshot_receipt,output):
    if output.exists():raise FileExistsError(output)
    sr=json.loads(snapshot_receipt.read_text());verify(sr['artifacts'])
    verify({p:d for p,d in sr['input_sha256'].items() if p!=str(raw)})
    if str(raw) not in sr['input_sha256']:raise ValueError('verified native RAW identity required')
    names,values=last_sample(raw,sr['source_file_fingerprint'])
    h=parsed(hierarchy.read_text());top=next(k for k in h if k.startswith('IntegerPLL_400MHz_PrototypeTop'))
    calls=[r for r in h[top][1] if r[0]=='instance' and r[2].startswith('IntegerPLL_DCO_')]
    if len(calls)!=1:raise ValueError('one physical DCO macro required')
    call=calls[0];meta=json.loads(metadata.read_text());wm=json.loads(wire_map.read_text());controls={}
    for port,node in zip(h[call[2]][0],call[3]):
        if not re.fullmatch(r'(DCO_THERM|COARSETHERMAL_CODE)\[\d+\]',port):continue
        old=meta['original_to_emitted'][top+'/'+node]
        controls[port]=dict(parent_logical_binding=node,original_emitted_node=old,
                            physical_driver_anchor=wm['capacitor_anchors'].get(old,old))
    expected={f'DCO_THERM[{i}]' for i in range(255)}|{f'COARSETHERMAL_CODE[{i}]' for i in range(47)}
    if controls.keys()!=expected:raise ValueError('complete 255 fine and 47 coarse control mapping required')
    text=isolated_deck.read_text()
    if not re.search(r'(?im)^\.param\s+VDD\s*=\s*1\.8\s*$',text):raise ValueError('1.8 V isolated bias bench required')
    sources={}
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].startswith(('VCTRL','VCOARSETHERM')):continue
        if len(f)!=4 or f[2]!='0' or f[3] not in ['0','{VDD}'] or f[1] in sources:raise ValueError('unambiguous static rail-valued control bias required')
        sources[f[1]]=1.8 if f[3]=='{VDD}' else 0.0
    if sources.keys()!=expected:raise ValueError('isolated bench bias vector incomplete')
    bound=bind(list(dict.fromkeys(v['physical_driver_anchor'] for v in controls.values())),names)
    if not bound['all_bound']:raise ValueError('every actual driver anchor must be saved in native RAW')
    mismatches=[];deviations=[]
    for port,c in controls.items():
        voltage=values[bound['bindings'][c['physical_driver_anchor']]['index']]
        c.update(native_final_V=voltage,isolated_bias_V=sources[port],binary_match=(voltage>=.9)==(sources[port]>=.9))
        deviations.append(abs(voltage-sources[port]))
        if not c['binary_match']:mismatches.append(port)
    pins={str(p):sha(p) for p in [hierarchy,metadata,wire_map,isolated_deck,snapshot_receipt,Path(__file__).resolve(),Path(__file__).with_name('check_selected_boundary_waveforms.py'),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py'),Path(__file__).with_name('capture_selected_native_initial_snapshot.py')]}
    verify(pins);pins[str(raw)]=sr['input_sha256'][str(raw)]
    save(output,dict(input_sha256=pins,controls=controls,control_count=len(controls),binary_mismatches=mismatches,
        final_binary_bias_vectors_match=not mismatches,maximum_final_driver_deviation_from_ideal_V=max(deviations),
        raw_rehashed_this_audit=False,raw_file_fingerprint_matches_verified_snapshot=True,
        terminal_binding_basis='parent logical control alias through native emitted and driver capacitance-anchor maps',
        driver_source_impedance_equivalent=False,transient_programming_equivalent=False,
        reduced_oscillator_frequency_correlated=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(controls=len(controls),binary_mismatches=mismatches,maximum_final_driver_deviation_from_ideal_V=max(deviations))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['hierarchy','metadata','wire-map','isolated-deck','raw','snapshot-receipt','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve() for n in ['hierarchy','metadata','wire-map','isolated-deck','raw','snapshot-receipt','output']))
