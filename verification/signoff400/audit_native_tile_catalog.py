#!/usr/bin/env python3
"""Independently check every catalog identity, source offset and basis descriptor."""
import argparse
from collections import Counter
import hashlib
import json
import mmap
from pathlib import Path
import time
from common import save, sha
from nominal_sheet_resistance_v3 import parse


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def audit_row(tile, row, number, offset, sheets, axis=None, axis_location=None):
    require(row['source_tile_row'] == number and row['source_tile_byte_offset'] == offset, 'tile row/offset')
    for key in ('native_group_id', 'tile_serial', 'native_working_plane_id', 'raw_type_id',
                'raw_material', 'original_conductor', 'box_internal', 'split', 'private_voltage_nodes'):
        require(row[key] == tile[key], 'native tile identity: '+key)
    for flag in ('native_snapshot_selection_qualified', 'full_C_attachment_qualified',
                 'material_device_interface_qualified', 'resistance_PVT_qualified',
                 'physical_RC_qualified', 'runtime_model_eligible', 'release_qualified'):
        require(row[flag] is False, 'qualification flag: '+flag)
    nodes = set(tile['private_voltage_nodes'])
    require(bool(nodes) and len(nodes) == len(tile['private_voltage_nodes']), 'unique nonempty native nodes')
    require(all(n.startswith('_rmesh_'+tile['native_group_id']+'_') for n in nodes), 'snapshot namespace')
    if len(nodes) > 1:
        require(axis is not None and axis_location is not None, 'axis reference required')
        require((row['axis_registry_row'], row['axis_registry_byte_offset']) == axis_location, 'axis location')
        for key in ('native_group_id', 'native_working_plane_id', 'raw_type_id', 'raw_material', 'original_conductor'):
            require(tile[key] == axis[key], 'axis identity: '+key)
        require(axis['tile_box_internal'] == tile['box_internal'], 'axis box')
        require({n for x, n in axis['native_voltage_knots']} == nodes, 'axis native voltage set')
        require(row['axis_preparation_state'] == axis['preparation_state'], 'axis state')
        ready = axis['geometric_axis_prepared'] and axis['numeric_end_resistors_complete']
        state = 'native_axis_candidate' if ready else 'deferred_native_axis'
        require('native_anchor_points' not in row, 'axis exposed as anchored sheet')
    else:
        require(axis is None and 'axis_registry_row' not in row and 'axis_registry_byte_offset' not in row,
                'single-voltage tile contains axis reference')
        box = tile['box_internal']
        anchors = {}
        for bp in tile['breakpoints']:
            point = tuple(bp['point_internal'])
            require(bp['private_id'] in nodes, 'anchor private identity')
            require(point not in anchors or anchors[point] == bp['private_id'], 'coincident anchor identity')
            anchors[point] = bp['private_id']
        require(bool(anchors), 'actual anchors required')
        if tile['split'] != 0 or box[0] >= box[2] or box[1] >= box[3]:
            state = 'deferred_anchor_shape'
        elif any(not (box[0] <= x <= box[2] and box[1] <= y <= box[3]) for x, y in anchors):
            state = 'deferred_outside_anchor'
        elif tile['raw_material'] not in sheets:
            state = 'deferred_anchor_material'
        else:
            state = 'anchored_sheet_candidate'
        ready = state == 'anchored_sheet_candidate'
        if ready:
            require(row['native_anchor_points'] == [[list(p), n] for p, n in sorted(anchors.items())], 'actual anchor locations')
            require(row['base_x_cuts_internal'] == sorted({box[0], box[2], *(p[0] for p in anchors)}), 'x grid cuts')
            require(row['base_y_cuts_internal'] == sorted({box[1], box[3], *(p[1] for p in anchors)}), 'y grid cuts')
            require(row['latent_node_namespace'] == f"_rmesh_sheet_{tile['native_group_id']}_{tile['tile_serial']}", 'latent namespace')
            require(row['nominal_sheet_milliohms_per_square'] == str(sheets[tile['raw_material']]), 'nominal rule value')
            require(row['mesh_family'] == 'Cartesian_P1_exact_anchor_cuts_LL_UR_diagonal', 'mesh family')
        else:
            require('native_anchor_points' not in row and 'mesh_family' not in row, 'deferred anchor descriptor exposed')
    require(row['catalog_state'] == state, 'catalog state')
    require(row['parameterized_basis_prepared'] is bool(ready), 'prepared flag')
    return state


def run(catalog, output):
    catalog, out = Path(catalog).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start, counts = time.monotonic(), Counter()
    save(out/'status.json', dict(state='independently_auditing_complete_tile_catalog', release_qualified=False))
    try:
        receipt = catalog/'assessment.json'
        c = json.loads(receipt.read_text())
        def unique(suffix):
            found = [Path(p) for p in c['input_sha256'] if p.endswith(suffix)]
            require(len(found) == 1, 'unique source pin: '+suffix)
            return found[0]
        tiles, axes, tech = (unique(s) for s in ('/tile_domains.jsonl', '/native/axis_registry.jsonl', '/sky130A.tech'))
        target = catalog/'native/tile_catalog.jsonl'
        sheets = parse(tech.read_text())
        pins = {str(p): sha(p) for p in (receipt, tech, Path(__file__).resolve(),
                *[Path(__file__).with_name(n) for n in ('common.py', 'nominal_sheet_resistance.py',
                'nominal_sheet_resistance_v2.py', 'nominal_sheet_resistance_v3.py')])}
        require(pins[str(tech)] == c['input_sha256'][str(tech)], 'technology changed')
        axis_offsets, used, seen_tiles = {}, set(), set()
        digest = hashlib.sha256()
        offset = 0
        with axes.open('rb') as stream:
            for number, raw in enumerate(stream, 1):
                axis_offsets[offset] = number
                digest.update(raw)
                offset += len(raw)
        require(digest.hexdigest() == c['input_sha256'][str(axes)], 'complete axis source hash')
        pins[str(axes)] = digest.hexdigest()
        tile_hash, catalog_hash = hashlib.sha256(), hashlib.sha256()
        offset = 0
        with axes.open('rb') as af, mmap.mmap(af.fileno(), 0, access=mmap.ACCESS_READ) as mapping, \
                tiles.open('rb') as source, target.open('rb') as records:
            for number, raw in enumerate(source, 1):
                if number % 1000 == 0:
                    require(time.monotonic()-start < 43200, 'catalog audit deadline')
                line = records.readline()
                require(bool(line), 'missing catalog row')
                tile, row = json.loads(raw), json.loads(line)
                key = (tile['native_group_id'], tile['tile_serial'])
                require(key not in seen_tiles, 'duplicate tile lifetime identity')
                seen_tiles.add(key)
                axis = location = None
                if len(tile['private_voltage_nodes']) > 1:
                    pos = row['axis_registry_byte_offset']
                    require(pos in axis_offsets and pos not in used, 'axis offset missing or reused')
                    used.add(pos)
                    end = mapping.find(b'\n', pos)
                    require(end >= pos, 'terminated axis record')
                    axis = json.loads(mapping[pos:end])
                    location = (axis_offsets[pos], pos)
                state = audit_row(tile, row, number, offset, sheets, axis, location)
                counts[state] += 1
                tile_hash.update(raw)
                catalog_hash.update(line)
                offset += len(raw)
            require(not records.read(1), 'extra catalog rows')
        require(len(used) == len(axis_offsets) == c['axis_records_matched_once'], 'all axes consumed exactly once')
        require(sum(counts.values()) == c['native_tiles'] and dict(counts) == c['catalog_state_counts'], 'catalog aggregate counts')
        require(tile_hash.hexdigest() == c['input_sha256'][str(tiles)], 'complete tile source hash')
        require(catalog_hash.hexdigest() == c['artifacts'][str(target)], 'complete catalog hash')
        pins.update({str(tiles): tile_hash.hexdigest(), str(target): catalog_hash.hexdigest()})
        for p, h in pins.items():
            require(sha(p) == h, 'audit input changed: '+p)
        result = dict(input_sha256=pins, all_native_tile_rows_independently_checked=True,
             native_tiles=sum(counts.values()), axis_records_consumed_once=len(used), catalog_state_counts=dict(counts),
             physical_RC_qualified=False, runtime_model_eligible=False, release_qualified=False,
             elapsed_s=time.monotonic()-start)
        save(out/'assessment.json', result)
        save(out/'status.json', dict(state='complete_tile_catalog_audit_passed_physical_RC_pending',
             release_qualified=False, elapsed_s=result['elapsed_s']))
        return result
    except BaseException as exc:
        save(out/'status.json', dict(state='failed', reason=repr(exc), release_qualified=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.catalog, a.output)))
