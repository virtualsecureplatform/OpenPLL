#!/usr/bin/env python3
"""Independent streaming audit of candidate axes; does not qualify physical RC."""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

from common import save, sha
from nominal_sheet_resistance import parse


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def audit_row(source, row, number, offset, sheets):
    require(row['source_chain_row'] == number and
            row['source_chain_byte_offset'] == offset, 'source row/byte offset')
    for key in ('native_group_id', 'original_conductor', 'native_working_plane_id',
                'raw_material', 'raw_type_id', 'tile_box_internal', 'flow_axis'):
        require(row[key] == source[key], 'source identity: ' + key)
    require(row['source_state'] == source['state'], 'source state')
    for flag in ('native_core_resistors_rewritten', 'native_snapshot_selection_qualified',
                 'material_device_interface_qualified', 'resistance_PVT_qualified',
                 'runtime_model_eligible', 'release_qualified'):
        require(row[flag] is False, 'unqualified flag: ' + flag)
    segments = source['segments']
    require(bool(segments) and row['native_segments_referenced'] == len(segments),
            'all native segments referenced')
    group = source['native_group_id']
    knots = [[segments[0][0], segments[0][2]]]
    for lo, hi, a, b, resistance, pointer in segments:
        require(a.startswith('_rmesh_' + group + '_') and
                b.startswith('_rmesh_' + group + '_'), 'snapshot identity')
        require(Fraction(resistance) >= 0, 'negative native resistance')
        knots.append([hi, b])
    require(row['native_voltage_knots'] == knots, 'native knots or aliases changed')
    axis, box = source['flow_axis'], source['tile_box_internal']
    inside = (source['state'] in ('full_tile_chain_positive_R',
              'full_tile_chain_with_zero_R', 'uncovered_tile_ends') and axis in (0, 1))
    inside = inside and all(s[0] < s[1] for s in segments)
    if inside:
        inside = (box[axis] <= knots[0][0] and knots[-1][0] <= box[axis + 2]
                  and box[1-axis] < box[3-axis])
    connected = all(a[1] == b[0] and a[3] == b[2]
                    for a, b in zip(segments, segments[1:]))
    zero = any(Fraction(s[4]) == 0 for s in segments)
    expected_ends = []
    candidate = [k[:] for k in knots]
    numeric = symbolic = 0
    if not inside:
        state = 'deferred_creation_geometry'
    elif not connected:
        state = 'deferred_chain_topology'
    elif zero:
        state = 'deferred_zero_R_constraint'
    else:
        for lower, bound, anchor in ((True, box[axis], knots[0]),
                                     (False, box[axis+2], knots[-1])):
            if bound == anchor[0]:
                continue
            node = f'_rmesh_axis_end_{group}_{number}_' + ('lo' if lower else 'hi')
            interval = [bound, anchor[0]] if lower else [anchor[0], bound]
            squares = Fraction(interval[1]-interval[0], box[3-axis]-box[1-axis])
            entry = dict(axis_interval_internal=interval,
                         endpoint_nodes=[node, anchor[1]] if lower else [anchor[1], node],
                         new_latent_node=node,
                         resistance_squares_exact=[str(squares.numerator), str(squares.denominator)])
            material = source['raw_material']
            if material in sheets:
                value = squares * sheets[material]
                entry['nominal_resistance_milliohms_exact'] = [str(value.numerator), str(value.denominator)]
                numeric += 1
            else:
                entry['requires_sheet_model_for_material'] = material
                symbolic += 1
            expected_ends.append(entry)
            if lower:
                candidate.insert(0, [bound, node])
            else:
                candidate.append([bound, node])
        state = ('axis_with_symbolic_end_resistance' if symbolic else
                 'axis_with_nominal_finite_ends' if numeric else 'native_full_axis_candidate')
    ready = inside and connected and not zero
    require(row['preparation_state'] == state, 'preparation state')
    require(row['geometric_axis_prepared'] is ready, 'prepared state')
    require(row['numeric_end_resistors_complete'] is (ready and not symbolic), 'numeric completeness')
    require(row['end_stub_resistors'] == expected_ends, 'finite/symbolic resistor construction')
    if ready:
        require(row['candidate_voltage_knots'] == candidate, 'candidate axis knots')
        require(candidate[0][0] == box[axis] and candidate[-1][0] == box[axis+2], 'tile coverage')
        require(all(a[0] < b[0] for a, b in zip(candidate, candidate[1:])), 'strict coverage')
    else:
        require('candidate_voltage_knots' not in row, 'deferred candidate exposed')
    return Counter(source_chains=1, native_segments_referenced=len(segments),
                   geometric_axes_prepared=int(ready), new_latent_end_states=len(expected_ends),
                   nominal_numeric_end_resistors=numeric, symbolic_end_resistors=symbolic), state


def audit_stream(source_path, registry_path, sheets, deadline):
    require(time.monotonic() < deadline, 'audit deadline')
    totals, states = Counter(), Counter()
    hashes = [hashlib.sha256(), hashlib.sha256()]
    offset = number = 0
    with Path(source_path).open('rb') as source, Path(registry_path).open('rb') as registry:
        for number, raw in enumerate(source, 1):
            if number % 1000 == 0:
                require(time.monotonic() < deadline, 'audit deadline')
            record = registry.readline()
            require(bool(record), 'missing registry row')
            counts, state = audit_row(json.loads(raw), json.loads(record), number, offset, sheets)
            totals.update(counts)
            states[state] += 1
            offset += len(raw)
            hashes[0].update(raw)
            hashes[1].update(record)
        require(number > 0 and not registry.read(1), 'empty source or extra registry rows')
    return dict(totals), dict(states), [h.hexdigest() for h in hashes]


def run(registry, output):
    registry, out = Path(registry).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    save(out/'status.json', dict(state='auditing_all_axis_rows', release_qualified=False))
    try:
        receipt = registry/'assessment.json'
        r = json.loads(receipt.read_text())
        sources = [Path(p) for p in r['input_sha256'] if p.endswith('/native/chains.jsonl')]
        techs = [Path(p) for p in r['input_sha256'] if p.endswith('/sky130A.tech')]
        require(len(sources) == len(techs) == 1, 'unique source chain and technology pins')
        source, tech = sources[0], techs[0]
        pins = {str(p): sha(p) for p in (receipt, tech, Path(__file__).resolve(),
                Path(__file__).with_name('nominal_sheet_resistance.py'), Path(__file__).with_name('common.py'))}
        require(pins[str(tech)] == r['input_sha256'][str(tech)], 'technology changed')
        target = registry/'native/axis_registry.jsonl'
        totals, states, hashes = audit_stream(source, target, parse(tech.read_text()), start+43200)
        require(hashes == [r['input_sha256'][str(source)], r['artifacts'][str(target)]], 'stream content hash')
        require(all(r[k] == v for k, v in totals.items()), 'aggregate counts')
        require(r['chains_by_preparation_state'] == states, 'aggregate states')
        for p, h in pins.items():
            require(sha(p) == h, 'audit input changed: ' + p)
        pins.update({str(source): hashes[0], str(target): hashes[1]})
        result = dict(input_sha256=pins, **totals, chains_by_preparation_state=states,
                      all_registry_rows_independently_checked=True,
                      physical_RC_qualified=False, runtime_model_eligible=False,
                      release_qualified=False, elapsed_s=time.monotonic()-start)
        save(out/'assessment.json', result)
        save(out/'status.json', dict(state='all_axis_rows_verified_physical_qualification_pending',
                                    release_qualified=False, elapsed_s=result['elapsed_s']))
        return result
    except BaseException as exc:
        save(out/'status.json', dict(state='failed', reason=repr(exc), release_qualified=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.registry, args.output)))
