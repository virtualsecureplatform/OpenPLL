"""Require explicit byte-level evidence when reusing an earlier conductor map."""
import json,time
from pathlib import Path
from common import ROOT,sha
from resources import lease


def bind_namespace(projection,mapping):
    proof=ROOT/'build/signoff400/startup_timing_final_projection_namespace_reconciliation_001/assessment.json';a=json.loads(proof.read_text());producer=projection/'assessment.json';mp=mapping/'assessment.json';p,m=[json.loads(x.read_text()) for x in (producer,mp)]
    if a['source_projection']!=str(projection) or a['source_mapping']!=str(mapping) or not a['both_final_node_maps_byte_identical'] or not a['independent_original_map_audit_bound'] or a['voltage_nodes']!=p['global_voltage_nodes'] or a['voltage_nodes']!=m['voltage_nodes']:raise ValueError('exact successful producer/map reconciliation required')
    pins={**a['input_sha256'],str(proof):sha(proof),str(Path(__file__).resolve()):sha(Path(__file__).resolve())}
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        if any(sha(x)!=h for x,h in pins.items()):raise ValueError('byte-identical namespace evidence changed')
    for row in a['namespace_files']:
        h=row['identical_sha256']
        if p['artifacts'].get(row['completed'])!=h or m['input_sha256'].get(row['old'])!=h or pins.get(row['completed'])!=h or pins.get(row['old'])!=h:raise ValueError('final node-map artifact lineage differs')
    return pins
