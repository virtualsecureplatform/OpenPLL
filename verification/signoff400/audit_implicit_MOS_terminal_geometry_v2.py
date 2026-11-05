"""Trace every zero-edge MOS terminal to retained terminal geometry and cell prototypes."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
import time
from common import save,sha,verify
from resources import lease


def parse(line):
    if not line.startswith('device msubckt '):return None
    f=re.split(r'"([^"]*)"',line);head=f[0].split()
    if len(f)!=9 or 'fet_' not in head[2]:return None
    parameters=dict(t.split('=',1) for t in head[7:] if '=' in t)
    if set(parameters)!={'l','w'}:raise ValueError('explicit native L/W geometry required')
    tails=[f[k].split() for k in (4,6,8)]
    if any(len(t)!=2 for t in tails):raise ValueError('native terminal geometry schema differs')
    return dict(model=head[2],point=list(map(int,head[3:5])),length=int(parameters['l']),width=int(parameters['w']),
                bulk=f[1],gate=f[3],source=f[5],drain=f[7],
                gate_edge=int(tails[0][0]),source_edge=int(tails[1][0]),drain_edge=int(tails[2][0]),
                gate_attribute=tails[0][1],source_attribute=tails[1][1],drain_attribute=tails[2][1])


def signature(r):
    return tuple(r[k] for k in ('model','length','width','gate_edge','source_edge','drain_edge',
                               'gate_attribute','source_attribute','drain_attribute'))


def run(fallback,extraction,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipt=fallback/'assessment.json';prior=json.loads(receipt.read_text())
    implicit=fallback/'implicit_terminals.jsonl'
    flat=next(Path(p) for p in prior['input_sha256'] if p.endswith('/Prototype400_FilledCapacitanceView.ext'))
    prototypes=sorted(extraction.glob('*.ext'))
    if not prototypes:raise ValueError('retained cell extraction prototypes required')
    paths=[receipt,implicit,flat,*prototypes,Path(__file__).resolve()]
    with lease(2,8,deadline):
        pins={str(p):sha(p) for p in paths}
        if pins[str(flat)]!=prior['input_sha256'][str(flat)] or pins[str(implicit)]!=prior['artifacts'][str(implicit)]:
            raise ValueError('implicit terminal geometry lineage changed')
        wanted={}
        for line in implicit.open():
            r=json.loads(line);key=(r['model'],*r['point_internal'])
            if key in wanted:raise ValueError('ambiguous implicit terminal coordinate')
            wanted[key]=r
        candidates=defaultdict(set)
        for p in prototypes:
            rows=[];hierarchical=False
            for line in p.open():
                if line.startswith('use '):hierarchical=True
                r=parse(line)
                if r is not None and r['source_edge']==0 and r['source_attribute']=='0':rows.append(r)
            if not hierarchical:
                for r in rows:candidates[signature(r)].add(p.stem)
        observed=set();counts=Counter();records=output/'terminal_geometry.jsonl';perimeter_fail=0
        with flat.open('rb') as source,records.open('w') as target:
            while True:
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('terminal geometry deadline')
                offset=source.tell();line=source.readline()
                if not line:break
                if not line.startswith(b'device msubckt '):continue
                r=parse(line.decode());
                if r is None:continue
                key=(r['model'],*r['point'])
                if key not in wanted:continue
                if key in observed:raise ValueError('duplicate flattened implicit device')
                observed.add(key);original=wanted[key]
                if (r['source_edge']!=0 or r['source_attribute']!='0' or r['source']!=r['bulk']
                        or original['terminal']!='source' or original['original_conductor']!=r['source']
                        or r['source']!=r['drain']):
                    raise ValueError('implicit source/bulk/drain alias geometry differs')
                match=sorted(candidates[signature(r)])
                if not match:
                    save(output/'unmatched_geometry.json',dict(device=r,signature=list(signature(r)),observed_devices=len(observed),candidate_signature_count=len(candidates)))
                    raise ValueError('no matching retained leaf-cell terminal geometry; see unmatched_geometry.json')
                ap=re.fullmatch(r'(\d+),(\d+)',r['drain_attribute'])
                if ap is None:raise ValueError('explicit drain area/perimeter required')
                area,perimeter=map(int,ap.groups())
                if area<=0 or r['width']<=0 or r['length']<=0 or r['drain_edge']!=2*r['width']:
                    raise ValueError('two gate-edge drain geometry differs')
                perimeter_fail+=perimeter<2*r['width']
                counts['|'.join(match)]+=1
                target.write(json.dumps(dict(r,source_flat_byte_offset=offset,matching_leaf_cell_geometry=match,
                    geometry_match_is_not_hierarchical_ownership_proof=True,
                    explicit_drain_area=area,explicit_drain_perimeter=perimeter,
                    combined_gate_adjacent_edge_length=2*r['width'],
                    residual_non_gate_perimeter=perimeter-2*r['width']))+'\n')
        if observed!=set(wanted):raise ValueError('incomplete implicit MOS geometry coverage')
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(records):sha(records)},
             all_implicit_MOS_terminal_geometry_traced=True,implicit_devices=len(observed),
             matching_leaf_geometry_counts=dict(counts),all_sources_have_zero_terminal_edge=True,
             all_original_source_drain_bulk_conductors_identical=True,
             all_nonzero_drain_edges_equal_two_channel_widths=True,
             negative_combined_non_gate_perimeter_cases=perimeter_fail,
             cell_matches_are_geometry_equivalence_not_instance_ownership=True,
             terminal_geometry_modified=False,simulator_or_foundry_models_changed=False,
             physical_spatial_junction_allocation_qualified=False,MOS_backend_compatibility_qualified=False,
             physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('fallback','extraction','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.fallback.resolve(),a.extraction.resolve(),a.output.resolve())
