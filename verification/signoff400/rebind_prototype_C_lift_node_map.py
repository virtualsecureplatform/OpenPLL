"""Recover model node names by exact byte replay of a completed C lift.

No native simulation or model change. This binds later boundary attachments to
actual emitted nodes rather than guessing anonymous SPICE node identities.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify
from build_prototype_full_C_wire_R_v5 import build
from join_prototype_physical_instances import dimensions,join


def run(extraction,rc,models,attachment,output):
    er,rr,mr=[p/'assessment.json' for p in (extraction,rc,models)]
    e,r,m=[json.loads(p.read_text()) for p in (er,rr,mr)]
    for record in (e,r,m):verify(record['input_sha256']);verify(record['artifacts'])
    if any(m['input_sha256'].get(str(p))!=sha(p) for p in (er,rr)):
        raise ValueError('same completed model construction inputs required')
    if not m['capacitance_lifts_are_exact_matrix_congruences']:raise ValueError('single voltage-map construction required')
    folder=Path(e['source_extraction_directory']);sources=list(folder.glob('*/capacitance.spice'))
    if len(sources)!=1:raise ValueError('one native analog hierarchy required')
    source=sources[0];top=source.parent.name;cell='sky130_fd_sc_hd__nand2_8'
    positions=rc/'placements.tsv';cell_ext=source.parent/(cell+'.ext');top_ext=source.parent/(top+'.ext')
    grid,controls=dimensions(cell_ext.read_text(),source.read_text(),cell)
    rows,scale=join(positions.read_text(),top_ext.read_text(),grid)
    mapping={re.sub(r'\\(.)',r'\1',row['routed_instance']):row['extracted_instance'] for row in rows}
    spef=rc/'nom.json';original=models/(attachment+'.spice');basis=models/(attachment+'.lift.json')
    if any(m['artifacts'].get(str(p))!=sha(p) for p in (original,basis)):
        raise ValueError('completed model and voltage-map artifacts required')
    model,metrics,lift=build(source.read_text(),top,json.loads(spef.read_text()),mapping,attachment)
    if hashlib.sha256(model.encode()).hexdigest()!=sha(original) or lift!=json.loads(basis.read_text()):
        raise ValueError('node recovery changed model bytes or voltage mapping')
    names=metrics.pop('emitted_node_map')
    voltage={node:names[point] for node,point in lift.items()}
    inputs={str(p):sha(p) for p in (er,rr,mr,source,positions,cell_ext,top_ext,spef,original,basis,
        Path(__file__).resolve(),Path(__file__).with_name('build_prototype_full_C_wire_R_v5.py'),
        Path(__file__).with_name('native_spice_comments.py'),Path(__file__).with_name('join_prototype_physical_instances.py'))}
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    save(output/'nodes.json',dict(emitted_node_names=names,original_capacitance_node_to_emitted_node=voltage,
        physical_instance_join=rows,magic_grid_um=str(grid),dimension_controls=controls))
    save(output/'assessment.json',dict(input_sha256=inputs,artifacts={str(output/'nodes.json'):sha(output/'nodes.json')},
        attachment=attachment,exact_completed_model_bytes_reproduced=True,
        exact_original_voltage_map_reproduced=True,model_changed=False,native_simulation_rerun=False,
        boundary_loading_attached=False,release_ready=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('extraction','rc','models','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--attachment',choices=('driver','farthest'),required=True)
    a=parser.parse_args();run(a.extraction.resolve(),a.rc.resolve(),a.models.resolve(),a.attachment,a.output.resolve())
