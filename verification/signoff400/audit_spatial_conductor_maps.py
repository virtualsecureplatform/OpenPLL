"""Verify every field and spatial voltage's original-conductor identity."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import mmap
from pathlib import Path
import re
import struct
import time
from common import save, sha
from resources import lease


def open_map(path, magic, count, nets):
    stream = path.open('rb')
    try:
        data = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        if data[:8] != magic or struct.unpack_from('<QQ', data, 8) != (count, nets) or len(data) != 24+4*count:
            raise ValueError('conductor map header/size')
        return stream, data
    except BaseException:
        stream.close()
        raise


def group(name):
    for pattern in (r'_rmesh_(\d+)_\d+', r'_rmesh_axis_end_(\d+)_\d+_(?:lo|hi)',
                    r'_rmesh_sheet_(\d+)_\d+:r1:\d+', r'_zero_R_(\d+)_\d+:(?:lo|hi)'):
        match = re.fullmatch(pattern, name)
        if match:
            return match[1]
    raise ValueError('unrecognized native/latent voltage namespace')


def run(mapping, output):
    mapping, out = mapping.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic()+43200
    receipt = mapping/'assessment.json'
    report = json.loads(receipt.read_text())
    config = mapping/'config.json'
    cfg = json.loads(config.read_text())
    inputs = [Path(cfg[key]) for key in ('fields', 'catalog', 'R_nodes', 'floating_nodes')]
    products = [mapping/'native'/name for name in ('field_nets.bin', 'voltage_nets.bin', 'net_names.jsonl')]
    paths = [receipt, config, *inputs, *products, Path(__file__).resolve()]
    with lease(2, 8, time.clock_gettime(time.CLOCK_BOOTTIME)+43200):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[str(p)] != report['input_sha256'][str(p)] for p in inputs):
            raise ValueError('conductor mapping source changed')
        if any(pins[str(p)] != report['artifacts'][str(p)] for p in products):
            raise ValueError('conductor mapping product changed')
        save(out/'status.json', dict(state='auditing_all_field_and_voltage_conductor_ids', release_qualified=False))
        names, lookup = [], {}
        with products[2].open() as rows:
            for raw in rows:
                number, name = json.loads(raw)
                if number != len(names) or name in lookup:
                    raise ValueError('unique contiguous conductor names')
                lookup[name] = number
                names.append(name)
        if len(names) != report['conductor_nets'] or names[0] != '@SUBSTRATE_REFERENCE':
            raise ValueError('conductor count/explicit reference')
        fs, fields = open_map(products[0], b'CNETFLD1', report['global_fields'], len(names))
        vs, voltages = open_map(products[1], b'CNETDOF1', report['voltage_nodes'], len(names))
        try:
            if struct.unpack_from('<I', voltages, 24)[0] != 0:
                raise ValueError('explicit reference voltage conductor')
            source_fields = json.loads(inputs[0].read_text())
            if len(source_fields) != report['global_fields']:
                raise ValueError('field source count')
            arithmetic = bytearray(len(source_fields))
            for field, row in enumerate(source_fields):
                if time.monotonic() > deadline:
                    raise TimeoutError('conductor map field audit deadline')
                if struct.unpack_from('<I', fields, 24+4*field)[0] != lookup[row[0]]:
                    raise ValueError('field conductor identity mismatch')
                arithmetic[field] = row[1] == 'arithmetic'
            del source_fields
            groups = {}
            with inputs[1].open() as rows:
                for raw in rows:
                    row = json.loads(raw)
                    key, conductor = row['native_group_id'], lookup[row['original_conductor']]
                    if key in groups and groups[key] != conductor:
                        raise ValueError('one conductor per native group')
                    groups[key] = conductor
            if len(groups) != report['selected_native_groups']:
                raise ValueError('selected native group count')
            last, identities = 0, set()
            with inputs[2].open() as rows:
                for raw in rows:
                    if time.monotonic() > deadline:
                        raise TimeoutError('R conductor map audit deadline')
                    number, name = json.loads(raw)
                    if number != last+1 or name in identities:
                        raise ValueError('unique contiguous R voltage identities')
                    if struct.unpack_from('<I', voltages, 24+4*number)[0] != groups[group(name)]:
                        raise ValueError('R voltage original conductor mismatch')
                    identities.add(name)
                    last = number
            if last != report['R_voltage_nodes']:
                raise ValueError('R voltage count')
            del identities
            last_field, floating_nodes = 0, 0
            with inputs[3].open() as rows:
                for raw in rows:
                    if time.monotonic() > deadline:
                        raise TimeoutError('floating conductor map audit deadline')
                    field, base, count = json.loads(raw)
                    if not 0 < field < report['global_fields'] or field <= last_field or arithmetic[field]:
                        raise ValueError('physical unique ordered floating field')
                    if base != last+1 or count <= 0 or base+count > report['voltage_nodes']:
                        raise ValueError('contiguous floating voltage range')
                    expected = fields[24+4*field:28+4*field]*count
                    if voltages[24+4*base:24+4*(base+count)] != expected:
                        raise ValueError('floating voltage conductor identity mismatch')
                    last = base+count-1
                    last_field = field
                    floating_nodes += count
            if last+1 != report['voltage_nodes'] or floating_nodes != report['floating_voltage_nodes']:
                raise ValueError('complete spatial voltage conductor coverage')
        finally:
            fields.close(); fs.close(); voltages.close(); vs.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('conductor map audit input changed')
        save(out/'assessment.json', dict(input_sha256=pins,
             all_field_and_voltage_conductor_ids_independently_checked=True,
             global_fields=report['global_fields'], voltage_nodes=report['voltage_nodes'],
             conductor_nets=report['conductor_nets'], explicit_reference_preserved=True,
             arithmetic_fields_allocate_no_voltage_states=True,
             source_projection_assessment_pending=report['source_projection_assessment_pending'],
             ideal_conductor_matrix_equivalence_checked=False, full_C_energy_matrix_assembled=False,
             physical_RC_qualified=False, release_qualified=False))
        save(out/'status.json', dict(state='all_conductor_map_identities_verified', release_qualified=False))
        print(json.dumps(dict(fields=report['global_fields'], voltages=report['voltage_nodes'], nets=len(names))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('mapping', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.mapping, args.output)
