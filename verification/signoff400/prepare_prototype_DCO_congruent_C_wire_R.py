"""Prepare explicitly nonlocal, passive congruent-C attachment diagnostics."""
import argparse,json,re
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from build_prototype_full_C_wire_R_v2 import build,expand
from prepare_prototype_analog_reference import subcircuits
from check_prototype_capacitance_paths import certify
from audit_hierarchical_capacitance import number
from project_prototype_fixed_rail_C import project, RAILS
from prepare_prototype_BBPD_receiver_v3 import header


def run(extraction,rc,certificate,output):
    er,rr,pr=[p/'assessment.json' for p in (extraction,rc,certificate)]
    e,r,p=[json.loads(f.read_text()) for f in (er,rr,pr)]
    for record in (e,r,p):verify(record['input_sha256']);verify(record['artifacts'])
    if not p['extracted_capacitor_networks_passive']:raise ValueError('fixed-supply dynamic C network must have an exact passivity certificate')
    source_dir=Path(e['source_extraction_directory']);files=list(source_dir.glob('*/capacitance.spice'))
    if len(files)!=1:raise ValueError('unique isolated analog hierarchy required')
    source=files[0];top=source.parent.name
    projection_receipts=[Path(f) for f in p['input_sha256'] if f.endswith('/assessment.json')]
    if len(projection_receipts)!=1:raise ValueError('unique ideal-supply projection receipt required')
    projection=json.loads(projection_receipts[0].read_text());verify(projection['input_sha256']);verify(projection['artifacts'])
    if not (projection.get('exact_fixed_voltage_congruence') and projection.get('complete_original_operator_independently_reparsed') and projection.get('supplies_exposed_as_top_ports') and projection.get('ideal_constant_supply_assumption')):raise ValueError('independent fixed-supply congruence required')
    aggregate_receipts=[Path(f) for f in projection['input_sha256'] if f.endswith('/assessment.json')]
    if len(aggregate_receipts)!=1:raise ValueError('unique original aggregation required')
    a=json.loads(aggregate_receipts[0].read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if a['input_sha256'].get(str(source))!=sha(source):raise ValueError('projection uses another extracted source')
    pairfiles=[Path(f) for f in a['artifacts'] if f.endswith('.pairs.jsonl')]
    projected_files=[Path(f) for f in p['input_sha256'] if f.endswith('.pairs.jsonl')]
    if len(pairfiles)!=1 or len(projected_files)!=1:raise ValueError('unique original/projected capacitor operators required')
    certified={tuple(x['nodes']):F(x['farads']) for line in pairfiles[0].read_text().splitlines() for x in [json.loads(line)]}
    dynamic={tuple(x['nodes']):F(x['farads']) for line in projected_files[0].read_text().splitlines() for x in [json.loads(line)]}
    if project(certified,set(projection['fixed_voltage_nodes']))!=dynamic:raise ValueError('exact source-to-certified-subspace identity failed')
    if expand(subcircuits(source.read_text()),top)[2]!=certified:raise ValueError('flattened operator differs from original signed C')
    join=rc/'join.json';mapping={re.sub(r'\\(.)',r'\1',row['routed_instance']):row['extracted_instance'] for row in json.loads(join.read_text())['mapping']}
    spef=rc/'nom.json'
    if r['artifacts'].get(str(spef))!=sha(spef):raise ValueError('parsed wire RC changed')
    physical={f:d for f,d in r['input_sha256'].items() if f.endswith('.gds')}
    if len(physical)!=1:raise ValueError('unique routed GDS identity required')
    output.mkdir(parents=True,exist_ok=False);paths=[er,rr,pr,*projection_receipts,*aggregate_receipts,*pairfiles,*projected_files,source,join,spef,Path(__file__).resolve(),Path(__file__).with_name('build_prototype_full_C_wire_R_v2.py')]
    pins={str(f):sha(f) for f in paths};results=[];artifacts={}
    for attachment in ('driver','farthest'):
        model,metrics,lift=build(source.read_text(),top,json.loads(spef.read_text()),mapping,attachment)
        if any(lift[n]!=n for n in RAILS[1:] if n in lift):raise ValueError('fixed-supply rails moved by congruence')
        pairs={}
        for line in subcircuits(model)[top].splitlines():
            f=line.split()
            if f and f[0].startswith('Cflat'):
                key=tuple(sorted(f[1:3]))
                if key in pairs:raise ValueError('duplicate generated flat capacitor')
                pairs[key]=number(f[3])
        proof=certify(pairs)
        proof_file=output/(attachment+'.passivity.json');save(proof_file,proof);artifacts[str(proof_file)]=sha(proof_file)
        if not set(RAILS[1:])<=set(header(subcircuits(model)[top])):raise ValueError('all fixed supply rails must be explicit top ports')
        dynamic_proof=certify(project(pairs,set(RAILS)))
        dynamic_file=output/(attachment+'.fixed_rail_passivity.json');save(dynamic_file,dynamic_proof);artifacts[str(dynamic_file)]=sha(dynamic_file)
        if not dynamic_proof['passivity_certified']:raise ValueError('congruent dynamic C operator lacks exact fixed-supply passivity certificate')
        metrics['unconstrained_supply_C_passivity_certified']=proof['passivity_certified']
        metrics['fixed_supply_dynamic_C_passivity_certified']=True
        target=output/(attachment+'.spice');target.write_text(model);basis=output/(attachment+'.lift.json');save(basis,lift)
        artifacts.update({str(f):sha(f) for f in (target,basis)})
        results.append(dict(model=str(target),**metrics))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
        candidate_gds_sha256=physical,original_full_hierarchical_capacitance_passivity_certified=False,original_fixed_supply_dynamic_capacitance_passivity_certified=True,capacitance_lifts_are_exact_matrix_congruences=True,
        cell_local_capacitance_at_actual_routed_pins=False,nonlocal_external_cell_fringe_C_attachment=True,each_fixed_supply_dynamic_C_operator_passivity_certified=True,
        ideal_constant_supply_assumption=True,nonideal_supply_behavior_qualified=False,
        zero_wire_R_topology_and_capacitance_operator_identity_verified=True,all_geometric_interactions_retained=True,
        native_attachment_variant_correlation_complete=False,cell_internal_wire_resistance_included=False,
        parent_loading_complete=False,wire_C_placement_uncertainty_bounded=False,diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('extraction','rc','certificate','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.extraction.resolve(),a.rc.resolve(),a.certificate.resolve(),a.output.resolve())
