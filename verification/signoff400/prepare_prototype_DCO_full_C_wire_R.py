"""Prepare independently checked full-geometric-C attachment variants for native correlation."""
import argparse,json,re
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from build_prototype_full_C_wire_R import build,expand
from prepare_prototype_analog_reference import subcircuits


def run(extraction,rc,certificate,output):
    er,rr,pr=[p/'assessment.json' for p in (extraction,rc,certificate)]
    e,r,p=[json.loads(f.read_text()) for f in (er,rr,pr)]
    for record in (e,r,p):verify(record['input_sha256']);verify(record['artifacts'])
    if not p['extracted_capacitor_networks_passive']:raise ValueError('original complete C network must have an exact passivity certificate')
    source_dir=Path(e['source_extraction_directory']);files=list(source_dir.glob('*/capacitance.spice'))
    if len(files)!=1:raise ValueError('unique isolated analog hierarchy required')
    source=files[0];top=source.parent.name
    aggregate_receipts=[Path(f) for f in p['input_sha256'] if f.endswith('/assessment.json')]
    if len(aggregate_receipts)!=1:raise ValueError('unique original capacitance aggregation receipt required')
    a=json.loads(aggregate_receipts[0].read_text())
    if a['input_sha256'].get(str(source))!=sha(source):raise ValueError('passivity proof uses another capacitance source')
    pairfiles=[Path(f) for f in p['input_sha256'] if f.endswith('.pairs.jsonl')]
    if len(pairfiles)!=1:raise ValueError('unique certified capacitor operator required')
    certified={tuple(x['nodes']):F(x['farads']) for line in pairfiles[0].read_text().splitlines() for x in [json.loads(line)]}
    if expand(subcircuits(source.read_text()),top)[2]!=certified:raise ValueError('flattened operator differs from independently certified C')
    join=rc/'join.json';mapping={re.sub(r'\\(.)',r'\1',row['routed_instance']):row['extracted_instance'] for row in json.loads(join.read_text())['mapping']}
    spef=rc/'nom.json'
    if r['artifacts'].get(str(spef))!=sha(spef):raise ValueError('parsed wire RC changed')
    output.mkdir(parents=True,exist_ok=False);paths=[er,rr,pr,*aggregate_receipts,*pairfiles,source,join,spef,Path(__file__).resolve(),Path(__file__).with_name('build_prototype_full_C_wire_R.py')]
    pins={str(f):sha(f) for f in paths};results=[];artifacts={}
    for attachment in ('driver','farthest'):
        model,metrics,lift=build(source.read_text(),top,json.loads(spef.read_text()),mapping,attachment)
        target=output/(attachment+'.spice');target.write_text(model);basis=output/(attachment+'.lift.json');save(basis,lift)
        artifacts.update({str(f):sha(f) for f in (target,basis)})
        results.append(dict(model=str(target),**metrics))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
        original_full_hierarchical_capacitance_passivity_certified=True,capacitance_lifts_are_exact_matrix_congruences=True,
        zero_wire_R_topology_and_capacitance_operator_identity_verified=True,all_geometric_interactions_retained=True,
        native_attachment_variant_correlation_complete=False,cell_internal_wire_resistance_included=False,
        parent_loading_complete=False,wire_C_placement_uncertainty_bounded=False,diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('extraction','rc','certificate','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.extraction.resolve(),a.rc.resolve(),a.certificate.resolve(),a.output.resolve())
