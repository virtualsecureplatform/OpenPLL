#!/usr/bin/env python3
"""Check every selected native zero-R chain against exact DC and mass oracles."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time
from common import ROOT, save, sha
from native_zero_R_axis_v2 import prepare, dc_matrix
from parallel_hash import sha_prefetch
from resources import lease


def solve(matrix,rhs):
    a=[list(map(F,row))+[F(b)] for row,b in zip(matrix,rhs)]
    for k in range(len(a)):
        pivot=next((i for i in range(k,len(a)) if a[i][k]),None)
        if pivot is None:raise ValueError('singular exact DC fixture')
        a[k],a[pivot]=a[pivot],a[k];scale=a[k][k]
        a[k]=[x/scale for x in a[k]]
        for i in range(len(a)):
            if i!=k:
                scale=a[i][k];a[i]=[x-scale*y for x,y in zip(a[i],a[k])]
    return [r[-1] for r in a]


def check_model(chain,namespace):
    m=prepare(chain,namespace)
    native=m['native_nodes'];source=native[0];load=native[-1]
    unknowns=native[1:]+m['latent_nodes']+[c['current_unknown'] for c in m['constraints']]
    # Synthetic normalized fixture only: source=1, unit native-R load to
    # reference. Original native branch values and zero constraints stay exact.
    matrix=dc_matrix(m,sheet_resistance=F(1));matrix[load,load]=matrix.get((load,load),F(0))+1
    rhs=[-matrix.get((n,source),F(0)) for n in unknowns]
    dense=[[matrix.get((n,k),F(0)) for k in unknowns] for n in unknowns]
    values=dict(zip(unknowns,solve(dense,rhs)));values[source]=F(1)
    current=1/(1+sum(e[2] for e in m['native_edges']))
    cumulative=F(0)
    for a,b,r,_ in m['native_edges']:
        if values[a]!=1-cumulative*current:raise ValueError('native series DC voltage mismatch')
        cumulative+=r
        if values[b]!=1-cumulative*current:raise ValueError('native series DC voltage mismatch')
        if r and (values[a]-values[b])/r!=current:raise ValueError('finite branch DC current mismatch')
    for c in m['constraints']:
        if values[c['positive']]!=values[c['negative']] or values[c['current_unknown']]!=current:
            raise ValueError('exact zero-voltage/current constraint mismatch')
    for n,b in zip(unknowns,rhs):
        if sum(matrix.get((n,k),F(0))*values[k] for k in unknowns)!=b:
            raise ValueError('nonzero original exact MNA residual')
    for e in m['symbolic_end_stub_resistors']:
        if values[e['new_latent_node']]!=values[e['anchor']]:
            raise ValueError('finite dangling end changes original native DC')
    basis=native+m['latent_nodes']
    mass=m['unit_area_mass'];names=basis+[m['reference']]
    if any(sum(mass.get((n,k),F(0)) for k in names) for n in names):raise ValueError('mass gauge failure')
    box=list(map(F,chain['tile_box_internal']));axis=chain['flow_axis'];width=box[3-axis]-box[1-axis]
    area=(box[2]-box[0])*(box[3]-box[1])
    if sum(mass.get((n,k),F(0)) for n in basis for k in basis)!=area:
        raise ValueError('unit-density mass area mismatch')
    energy=sum(v*values.get(a,F(0))*values.get(b,F(0)) for (a,b),v in mass.items())
    quadrature=F(0)
    for (lo,a),(hi,b) in zip(m['knots'],m['knots'][1:]):
        va,vb=values[a],values[b]
        quadrature+=width*(hi-lo)*(va*va+4*((va+vb)/2)**2+vb*vb)/6
    if energy!=quadrature or energy<=0:raise ValueError('independent strip quadrature mismatch')
    return dict(native_nodes=len(native),native_segments=len(m['native_edges']),
                zero_voltage_constraints=len(m['constraints']),exact_DC_residual='0',
                latent_end_states=len(m['latent_nodes']),synthetic_sheet_parameter='1',
                symbolic_material_end_resistors_retained=True,
                unit_density_charge_mass_exact=True,synthetic_normalized_load_fixture=True,
                zero_constraints=[{k:v for k,v in c.items() if k!='voltage_rhs'} for c in m['constraints']],
                physical_RC_qualified=False,resistance_PVT_qualified=False,release_qualified=False)


def run(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    catalog=a.catalog.resolve();cr=catalog/'assessment.json';c=json.loads(cr.read_text())
    audit=a.audit.resolve()/'assessment.json';v=json.loads(audit.read_text())
    source=catalog/'native/tile_catalog.jsonl'
    if not v['all_source_rows_independently_partitioned'] or v['input_sha256'].get(str(cr))!=sha(cr):
        raise ValueError('complete matching independent selected-catalog audit required')
    all_catalog=Path(c['source_catalog'])/'assessment.json'
    if c['input_sha256'].get(str(all_catalog))!=sha(all_catalog):
        raise ValueError('selected catalog source receipt changed')
    producer=json.loads(all_catalog.read_text())
    matches=[Path(p) for p in producer['input_sha256'] if p.endswith('/native/axis_registry.jsonl')]
    if len(matches)!=1:raise ValueError('unique catalog-bound axis registry required')
    axes=matches[0];ar=axes.parent.parent/'assessment.json';r=json.loads(ar.read_text())
    matches=[Path(p) for p in r['input_sha256'] if p.endswith('/native/chains.jsonl')]
    if len(matches)!=1:raise ValueError('unique registry-bound chain source required')
    chains=matches[0]
    if producer['input_sha256'].get(str(ar))!=sha(ar):raise ValueError('catalog axis receipt changed')
    paths=[cr,audit,all_catalog,ar,axes,chains,source,Path(__file__).resolve(),
           *[Path(__file__).with_name(n) for n in ('native_zero_R_axis_v2.py','native_axis_basis.py','common.py','parallel_hash.py','resources.py')]]
    with lease(8,16,deadline):
        save(out/'status.json',dict(state='hashing_and_selecting_native_zero_R_axes',release_qualified=False))
        with ThreadPoolExecutor(max_workers=4) as pool:
            hashes=list(pool.map(lambda p:sha_prefetch(p,readers=2,deadline=deadline),paths))
        pins=dict(zip(map(str,paths),hashes))
        if pins[str(source)]!=v['input_sha256'][str(source)] or pins[str(axes)]!=r['artifacts'][str(axes)] or pins[str(axes)]!=producer['input_sha256'][str(axes)]:
            raise ValueError('audited catalog/axis source changed')
        if r['input_sha256'].get(str(chains))!=pins[str(chains)]:raise ValueError('native chain source changed')
        wanted=[];digest=hashlib.sha256()
        with source.open('rb') as stream:
            for raw in stream:
                digest.update(raw);item=json.loads(raw)
                if item.get('axis_preparation_state')=='deferred_zero_R_constraint':wanted.append(item)
        if digest.hexdigest()!=pins[str(source)] or not wanted:raise ValueError('catalog changed or no zero-R axes')
        records=[]
        with axes.open('rb') as axis_stream,chains.open('rb') as chain_stream:
            for tile in wanted:
                axis_stream.seek(tile['axis_registry_byte_offset']);axis=json.loads(axis_stream.readline())
                if (axis['native_group_id'],axis['tile_box_internal'],axis['preparation_state'])!=(tile['native_group_id'],tile['box_internal'],'deferred_zero_R_constraint'):
                    raise ValueError('axis/catalog reference mismatch')
                chain_stream.seek(axis['source_chain_byte_offset']);chain=json.loads(chain_stream.readline())
                if (chain['native_group_id'],chain['tile_box_internal'])!=(axis['native_group_id'],axis['tile_box_internal']):
                    raise ValueError('native chain/axis identity mismatch')
                result=check_model(chain,'_zero_R_'+tile['native_group_id']+'_'+str(tile['tile_serial']))
                records.append(dict(tile_serial=tile['tile_serial'],group=tile['native_group_id'],
                    source_axis_byte_offset=tile['axis_registry_byte_offset'],source_chain_byte_offset=axis['source_chain_byte_offset'],**result))
        save(out/'cases.json',records)
        for p,h in pins.items():
            if sha_prefetch(Path(p),readers=4,deadline=deadline)!=h:raise ValueError('control input changed')
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(out/'cases.json'):sha(out/'cases.json')},
            selected_native_chains=len(records),native_segments=sum(x['native_segments'] for x in records),
            zero_voltage_constraints=sum(x['zero_voltage_constraints'] for x in records),
            latent_end_states=sum(x['latent_end_states'] for x in records),
            end_sheet_parameter_is_synthetic=True,diode_material_model_qualified=False,
            all_exact_DC_controls_pass=True,all_unit_density_mass_controls_pass=True,
            epsilon_resistance_added=False,native_voltage_identities_preserved=True,
            physical_RC_qualified=False,resistance_PVT_qualified=False,release_qualified=False))
        save(out/'status.json',dict(state='native_zero_R_axis_controls_complete',release_qualified=False))
        print(json.dumps(dict(chains=len(records),constraints=sum(x['zero_voltage_constraints'] for x in records))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','audit','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
