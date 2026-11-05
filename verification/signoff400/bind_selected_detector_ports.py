"""Bind five detector signal terminals using the proved wire-contraction map.

Logical anchors can disappear after R insertion; never guess a terminal from
its old node spelling or treat extra hierarchical ports as voltage inputs.
"""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify

SIGNALS=('REF','CLKDIVR','RESET_N','BBPD[0]','BBPD[1]')


def bind(inventory,original_nodes,wire_map):
    selected=set(inventory['detector_signal_nodes']);source=wire_map['generated_node_to_source_conductor'];result={}
    for logical in SIGNALS:
        original=inventory['logical_parent_bindings'][logical]
        candidates={original_nodes[k] for k in [original,'IntegerPLL_400MHz_PrototypeTop/'+original] if k in original_nodes}
        if len(candidates)!=1:raise ValueError('unique original parent anchor required: '+logical)
        anchor=next(iter(candidates));edges=[]
        for edge in inventory['wire_edges_crossing_detector_node_set']:
            conductors={source.get(n,n) for n in edge['nodes']}
            if conductors=={anchor}:edges.append(edge)
        if len(edges)!=1:raise ValueError('unique macro signal wire crossing required: '+logical)
        edge=edges[0];inside=[n for n in edge['nodes'] if n in selected]
        if len(inside)!=1:raise ValueError('unique macro-side terminal required')
        result[logical]=dict(parent_logical_node=original,original_emitted_conductor=anchor,
            detector_wire_endpoint=inside[0],outside_wire_endpoint=next(n for n in edge['nodes'] if n!=inside[0]),
            crossing_wire_resistor=edge)
    if len({v['detector_wire_endpoint'] for v in result.values()})!=5:raise ValueError('detector signal terminals are not distinct')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['inventory','metadata','wire-map','output']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    inventory=json.loads(a.inventory.read_text());verify(inventory['input_sha256'])
    metadata=json.loads(a.metadata.read_text());wire_map=json.loads(a.wire_map.read_text())
    if inventory['input_sha256'].get(str(a.metadata.resolve()))!=sha(a.metadata):raise ValueError('metadata does not match detector inventory')
    receipt=a.wire_map.parent/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    wire_model=a.wire_map.parent/'context.spice'
    if r['artifacts'].get(str(a.wire_map.resolve()))!=sha(a.wire_map) or inventory['input_sha256'].get(str(wire_model.resolve()))!=sha(wire_model):raise ValueError('proved wire map must match inventoried native graph')
    ports=bind(inventory,metadata['original_to_emitted'],wire_map)
    pins={str(p.resolve()):sha(p) for p in [a.inventory,a.metadata,a.wire_map,receipt,Path(__file__).resolve()]}
    verify(pins)
    save(a.output,dict(input_sha256=pins,ports=ports,physical_signal_ports_bound=True,
        basis='unique source-conductor identity at each macro-side wire-R crossing',
        finite_slew_stimuli_validated=False,receiver_loading_validated=False,active_detector_phase_validation_complete=False,
        physical_models_qualified=False,release_ready=False))
    print(json.dumps({k:v['detector_wire_endpoint'] for k,v in ports.items()}))
