"""Identify the abstract reference with the declared substrate for ideal comparisons."""
import argparse
from array import array
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
from common import save, sha
from compiled_charge import execute
from resources import lease


def write_map(path, count, substrate):
    if sys.byteorder != 'little' or array('I').itemsize != 4:
        raise ValueError('explicit little-endian 32-bit map host required')
    if not 0 < substrate < count:
        raise ValueError('distinct substrate conductor required')
    # Keep reference 0; remove substrate's old slot from all higher IDs.
    values = array('I', (0 if i == substrate else i-(i > substrate) for i in range(count)))
    with path.open('wb') as stream:
        stream.write(b'CNETDOF1'+struct.pack('<QQ', count, count-1))
        values.tofile(stream)
    # Independently verify the complete serialization, collision and coverage.
    data = path.read_bytes()
    assert data[:8] == b'CNETDOF1' and len(data) == 24+4*count
    assert struct.unpack_from('<QQ', data, 8) == (count, count-1)
    seen = bytearray(count-1)
    aliases = 0
    for old, (new,) in enumerate(struct.iter_unpack('<I', data[24:])):
        expected = old if old < substrate else old-1
        if old == substrate:
            expected = 0
        assert new == expected
        aliases += bool(seen[new])
        seen[new] = 1
    assert aliases == 1 and all(seen)


def run(reference, binding, mapping, controls, merger_upgrade, output):
    reference, binding, mapping, controls, merger_upgrade, out = (p.resolve() for p in
        (reference, binding, mapping, controls, merger_upgrade, output))
    out.mkdir(parents=True, exist_ok=False)
    scratch = Path(tempfile.mkdtemp(prefix='openpll-ideal-substrate-fold-', dir='/tmp'))
    (out/'native').symlink_to(scratch, target_is_directory=True)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipts = [p/'assessment.json' for p in (reference, binding, mapping, controls, merger_upgrade)]
    ref, bind, maps, ctl, upgrade = [json.loads(p.read_text()) for p in receipts]
    if not ctl['spatial_conductor_collapse_controls_pass'] or not upgrade['actual_operator_merge_bytes_identical']:
        raise ValueError('controlled collapse and merger required')
    if not bind['native_ideal_comparison_requires_reference_substrate_identification']:
        raise ValueError('native substrate binding proof required')
    if bind['input_sha256'].get(str(receipts[0])) != sha(receipts[0]):
        raise ValueError('substrate/reference lineage differs')
    if bind['input_sha256'].get(str(receipts[2])) != sha(receipts[2]):
        raise ValueError('substrate/conductor-map lineage differs')
    count, substrate = ref['conductor_nets'], bind['native_substrate_conductor_id']
    if maps['conductor_nets'] != count or bind['abstract_reference_conductor_id'] != 0:
        raise ValueError('conductor counts or reference identity differ')
    binary, merger = controls/'collapse_spatial_matrix', Path(upgrade['merger_binary'])
    names = mapping/'native/net_names.jsonl'
    matrices = {label: Path(ref[key]) for label, key in (
        ('physical_integral', 'physical_integral_reference_matrix'),
        ('native_trace_delta', 'native_output_reference_matrix'))}
    expected = {str(binary): ctl['artifacts'][str(binary)],
                str(merger): upgrade['input_sha256'][str(merger)],
                str(names): maps['artifacts'][str(names)],
                **{str(p): ref['artifacts'][str(p)] for p in matrices.values()}}
    paths = [*receipts, *map(Path, expected), Path(__file__).resolve()]
    artifacts, results = {}, {}
    with lease(8, 16, deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[p] != h for p, h in expected.items()):
            raise ValueError('substrate-fold input changed')
        for n, s in ((2, 1), (7, 1), (7, 3), (7, 6)):
            write_map(out/f'control_{n}_{s}.bin', n, s)
        voltage_map = out/'ideal_substrate_map.bin'
        write_map(voltage_map, count, substrate)
        folded_names = out/'ideal_net_names.jsonl'
        found = False
        with names.open() as source, folded_names.open('w') as target:
            for old, line in enumerate(source):
                number, name = json.loads(line)
                if number != old:
                    raise ValueError('noncontiguous conductor identities')
                if number == substrate:
                    if name != bind['declared_native_substrate']:
                        raise ValueError('declared substrate name differs')
                    found = True
                    continue
                target.write(json.dumps([number-(number > substrate),
                    bind['declared_native_substrate'] if number == 0 else name])+'\n')
        if not found or old+1 != count:
            raise ValueError('complete conductor names required')
        for label, matrix in matrices.items():
            cfg = out/(label+'.collapse.json')
            save(out/'status.json', dict(state='folding_ideal_substrate', matrix=label, release_qualified=False))
            save(cfg, dict(matrix=str(matrix), voltage_map=str(voltage_map), threads=8,
                 max_accumulator_entries=1000000, output=str(scratch/label), deadline_uptime=deadline))
            execute([binary, cfg], out/(label+'.collapse.log'), deadline, 16)
            summary = json.loads((out/(label+'.collapse.log')).read_text())
            current = sorted((scratch/label).glob('*.bin'))
            if len(current) != summary['sparse_runs'] or not current or summary['conductor_nets'] != count-1:
                raise ValueError('incomplete folded matrix runs')
            artifacts.update({str(p): sha(p) for p in current})
            level = 0
            while len(current) > 1:
                next_level = []
                for start in range(0, len(current), 128):
                    merged = scratch/f'{label}_{level}_{start}.bin'
                    merge_cfg = scratch/f'{label}_{level}_{start}.json'
                    save(merge_cfg, dict(inputs=list(map(str, current[start:start+128])),
                         output=str(merged), deadline_uptime=deadline))
                    execute([merger, merge_cfg], scratch/f'{label}_{level}_{start}.log', deadline, 2)
                    artifacts[str(merged)] = sha(merged)
                    next_level.append(merged)
                current = next_level
                level += 1
            results[label] = str(current[0])
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('substrate-fold input changed during execution')
        artifacts.update({str(p): sha(p) for p in (voltage_map, folded_names)})
        save(out/'assessment.json', dict(input_sha256=pins, artifacts=artifacts,
             ideal_substrate_reference_matrices_prepared=True, folded_matrices=results,
             source_conductor_nets=count, ideal_native_conductor_nets=count-1,
             identified_old_conductors=[0, substrate], declared_substrate=bind['declared_native_substrate'],
             complete_map_serialization_independently_checked=True,
             scope='ideal original-conductor comparison only; no spatial voltages merged',
             full_printed_native_matrix_reconstruction_verified=False,
             finite_R_substrate_target_assignment_qualified=False,
             scalar_rounding_spatial_assignment_complete=False,
             global_passivity_qualified=False, physical_RC_qualified=False, release_qualified=False))
        save(out/'status.json', dict(state='ideal_substrate_references_prepared', release_qualified=False))
        print(json.dumps(dict(ideal_native_conductors=count-1, matrices=results)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'binding', 'mapping', 'controls', 'merger-upgrade', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.binding, args.mapping, args.controls, args.merger_upgrade, args.output)
