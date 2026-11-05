"""Prepare ideal-conductor collapse maps without treating a live pass as complete."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease, identity


def run(projection, compiled, controls, output):
    projection, compiled, controls, out = (p.resolve() for p in (projection, compiled, controls, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    manifest = projection/'input_manifest.json'
    pins_expected = json.loads(manifest.read_text())['input_sha256']
    p_cfg = projection/'config.json'
    full = json.loads(p_cfg.read_text())
    control_receipt, control_cfg = controls/'assessment.json', controls/'stream.config.json'
    checked = json.loads(control_receipt.read_text())
    if not checked['streamed_sparse_accumulation_controls_pass'] or pins_expected.get(str(control_receipt)) != sha(control_receipt):
        raise ValueError('projection/control lineage mismatch')
    if pins_expected.get(str(control_cfg)) != sha(control_cfg):
        raise ValueError('projection control configuration changed')
    a, b = (dict(x['geometry']) for x in (full, json.loads(control_cfg.read_text())))
    a.pop('deadline_uptime'); b.pop('deadline_uptime')
    if a != b:
        raise ValueError('projection and controlled geometry differ')
    completed = (projection/'assessment.json').exists()
    if not completed:
        process = json.loads((projection/'native.process.json').read_text())
        if identity(process['pid']) != process['birth']:
            raise ValueError('source projection is neither completed nor verified live')
        # These maps are closed before any shard status is written by this producer.
        if not list((projection/'native').glob('shard_*.status.json')):
            raise ValueError('projection has not completed node-map startup')
    receipt = compiled/'assessment.json'
    c = json.loads(receipt.read_text())
    if pins_expected.get(str(receipt)) != sha(receipt):
        raise ValueError('projection compiler receipt changed')
    R_receipt = Path(full['geometry']['R_index']).parent/'assessment.json'
    r = json.loads(R_receipt.read_text())
    if pins_expected.get(str(R_receipt)) != sha(R_receipt):
        raise ValueError('projection R geometry receipt changed')
    fields, catalog = compiled/'fields.json', Path(r['catalog'])
    R_nodes, floating = [(projection/'native'/name).resolve() for name in ('R_nodes.jsonl', 'floating_nodes.jsonl')]
    source = ROOT/'tools/sheet_charge/prepare_conductor_maps.cpp'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [manifest, p_cfg, control_receipt, control_cfg, receipt, R_receipt, fields, catalog,
             R_nodes, floating, source, compiler, ROOT/'tools/charge_compiler/json.hpp', Path(__file__).resolve()]
    with lease(4, 8, deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if pins[str(fields)] != c['artifacts'][str(fields)] or pins[str(catalog)] != r['input_sha256'][str(catalog)]:
            raise ValueError('conductor mapping geometry/fields source changed')
        binary = out/'prepare_conductor_maps'
        execute([compiler, '-std=c++20', '-O3', '-Wall', '-Wextra', '-Wpedantic', source, '-o', binary],
                out/'build.log', deadline, 8)
        cfg = out/'config.json'
        save(cfg, dict(fields=str(fields), catalog=str(catalog), R_nodes=str(R_nodes),
             floating_nodes=str(floating), voltage_nodes=checked['compiled_summary']['global_voltage_nodes'],
             output=str(out/'native'), deadline_uptime=deadline))
        save(out/'status.json', dict(state='mapping_all_spatial_voltages_to_original_conductors', release_qualified=False))
        execute([binary, cfg], out/'native.log', deadline, 8)
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('conductor map input changed')
        result = json.loads((out/'native.log').read_text())
        artifacts = [binary, cfg, out/'native.log', *sorted((out/'native').glob('*'))]
        save(out/'assessment.json', dict(**result, input_sha256=pins,
             artifacts={str(p): sha(p) for p in artifacts}, source_projection=str(projection),
             source_projection_assessment_pending=not completed,
             conductor_collapse_maps_prepared=True, independent_map_audit_complete=False,
             arithmetic_fields_mapped_only_for_scalar_bookkeeping=True,
             ideal_conductor_matrix_equivalence_checked=False, full_C_energy_matrix_assembled=False))
        save(out/'status.json', dict(state='conductor_maps_prepared_parent_and_equivalence_checks_pending', release_qualified=False))
        print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('projection', 'compiled', 'controls', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.projection, args.compiled, args.controls, args.output)
