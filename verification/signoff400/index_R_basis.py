"""Pin the corrected R geometry chain and build a compact field/bundle index."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(mapping, audit, output):
    mapping, audit, out = (p.resolve() for p in (mapping, audit, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipt, proof = mapping/'assessment.json', audit/'assessment.json'
    report, checked = (json.loads(p.read_text()) for p in (receipt, proof))
    if not checked['all_field_associations_independently_checked'] or checked['input_sha256'].get(str(receipt)) != sha(receipt):
        raise ValueError('matching full R map audit required')
    catalog = Path(report['source_catalog'])
    cr = catalog/'assessment.json'
    c = json.loads(cr.read_text())
    if report['input_sha256'].get(str(cr)) != sha(cr):
        raise ValueError('R map/catalog mismatch')
    all_catalog = Path(c['source_catalog'])/'assessment.json'
    ac = json.loads(all_catalog.read_text())
    if c['input_sha256'].get(str(all_catalog)) != sha(all_catalog):
        raise ValueError('selected/source catalog mismatch')
    axes = [Path(p) for p in ac['input_sha256'] if p.endswith('/native/axis_registry.jsonl')]
    if len(axes) != 1:
        raise ValueError('unique catalog-bound axis registry required')
    axes = axes[0]
    ar = axes.parent.parent/'assessment.json'
    a = json.loads(ar.read_text())
    if ac['input_sha256'].get(str(ar)) != sha(ar):
        raise ValueError('catalog/axis registry mismatch')
    chains = [Path(p) for p in a['input_sha256'] if p.endswith('/native/chains.jsonl')]
    if len(chains) != 1:
        raise ValueError('unique registry-bound chain source required')
    chains = chains[0]
    fields, bundles = (mapping/'native'/name for name in ('field_domains.jsonl', 'R_tile_bundles.jsonl'))
    tiles = catalog/'native/tile_catalog.jsonl'
    expected = {str(p): report['artifacts'][str(p)] for p in (fields, bundles)}
    expected.update({str(tiles): c['artifacts'][str(tiles)], str(axes): a['artifacts'][str(axes)],
                     str(chains): a['input_sha256'][str(chains)]})
    cpp = ROOT/'tools/sheet_charge/index_R_basis.cpp'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [receipt, proof, cr, all_catalog, ar, cpp, compiler, ROOT/'tools/charge_compiler/json.hpp',
             Path(__file__).resolve(), *map(Path, expected)]
    with lease(8, 8, deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[p] != h for p, h in expected.items()):
            raise ValueError('R basis source changed')
        binary, cfg = out/'index_R_basis', out/'config.json'
        execute([compiler, '-std=c++20', '-O3', '-Wall', '-Wextra', '-Wpedantic', cpp, '-o', binary],
                out/'build.log', deadline, 8)
        save(cfg, dict(fields=str(fields), bundles=str(bundles), index=str(out/'fields.idx'), deadline_uptime=deadline))
        save(out/'status.json', dict(state='indexing_corrected_R_fields', release_qualified=False))
        execute([binary, cfg], out/'native.log', deadline, 8)
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('R basis source changed during indexing')
        result = json.loads((out/'native.log').read_text())
        if result['R_fields'] != report['R_tile_bundles'] or result['global_fields'] != report['global_fields']:
            raise ValueError('R field coverage')
        save(out/'assessment.json', dict(**result, input_sha256=pins,
             artifacts={str(p): sha(p) for p in (binary, cfg, out/'fields.idx', out/'native.log')},
             source_mapping=str(mapping), source_audit=str(audit), catalog=str(tiles), axes=str(axes),
             chains=str(chains), bundles=str(bundles), index_format='RBSIDX01_le_u64_count_then_u64_offset_u32_length_u32_bundle',
             physical_RC_qualified=False, full_C_energy_matrix_assembled=False))
        save(out/'status.json', dict(state='corrected_R_basis_index_complete', release_qualified=False))
        print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('mapping', 'audit', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.mapping, args.audit, args.output)
