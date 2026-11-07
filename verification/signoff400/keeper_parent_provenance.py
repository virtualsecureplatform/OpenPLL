"""Resolve the checked fresh parent stream behind an unfilled or filled candidate."""
import json
from pathlib import Path
from common_v3 import sha,verify


def resolve(assembly,record):
    if record.get('fresh_parent_route_streamed'):
        return record,[]
    if not all(record.get(k)for k in ['all_original_parent_geometry_and_labels_preserved','only_fill_purpose_layers_added','fill_preparation_only','unfilled_parent_DRC_pass','unfilled_parent_LVS_pass']):
        raise ValueError('fresh stream or geometry-preserving fill of a checked fresh stream required')
    candidates=[]
    for file in record['input_sha256']:
        p=Path(file)
        if not file.endswith('/assessment.json'):continue
        r=json.loads(p.read_text())
        if r.get('fresh_parent_route_streamed'):candidates.append((p,r))
    if len(candidates)!=1:raise ValueError('unique checked parent stream required')
    source,origin=candidates[0];verify(origin['input_sha256']);verify(origin['artifacts'])
    gds=source.parent/'assembly.gds'
    if record['input_sha256'].get(str(gds))!=sha(gds):raise ValueError('filled source GDS differs')
    if not origin['all_source_macro_geometry_and_labels_preserved']or not origin['macro_positions_unchanged']:
        raise ValueError('source macro geometry or placements not preserved')
    return origin,[source]
