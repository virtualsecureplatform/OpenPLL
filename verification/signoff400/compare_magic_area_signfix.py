"""Compare the isolated area-sign candidate against completed native controls."""
import argparse
import json
import math
from pathlib import Path
from common_v3 import save, sha, verify
from probe_magic_resistance_area_trace import signature


def events(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def run(baseline_local, baseline_broad, candidate_local, candidate_broad,
        baseline_engine, engine, output):
    roots = [baseline_local, baseline_broad, candidate_local, candidate_broad]
    receipts = [p / 'assessment.json' for p in [*roots, baseline_engine, engine]]
    a, b, c, d, old, new = [json.loads(p.read_text()) for p in receipts]
    for r in (a, b, c, d, old, new):
        verify(r['input_sha256'])
        verify(r['artifacts'])
    if old['capacitance_equations_modified'] or new.get('single_breakpoint_area_sign_corrected') is not True:
        raise ValueError('unmodified baseline and explicitly corrected candidate required')
    if new['capacitance_equations_modified'] is not True or new['release_tool_replaced']:
        raise ValueError('isolated candidate arithmetic metadata required')
    for r, receipt in [(a, receipts[4]), (b, receipts[4]), (c, receipts[5]), (d, receipts[5])]:
        if r['input_sha256'].get(str(receipt)) != sha(receipt):
            raise ValueError('matching active engine receipt required')
    if not all(r['all_six_native_controls_complete'] for r in (a, b, c)) or not d['all_two_native_controls_complete']:
        raise ValueError('completed fixture families required')
    pins = {str(p): sha(p) for p in [*receipts, Path(__file__).resolve(),
                                    Path(__file__).with_name('probe_magic_resistance_area_trace.py'),
                                    Path(__file__).with_name('audit_keeper_native_R_contraction.py')]}
    results = []
    checks = []
    cases = [(baseline_local, candidate_local, name, name == 'dangling_tee')
             for name in ('horizontal', 'vertical', 'dangling_tee')]
    cases.append((baseline_broad, candidate_broad, 'dangling_tee', False))
    for before, after, name, corrected_case in cases:
        x, y = before / (name + '_on'), after / (name + '_on')
        source_receipts = {baseline_local: a, baseline_broad: b, candidate_local: c, candidate_broad: d}
        for root, folder in ((before, x), (after, y)):
            manifest = source_receipts[root]
            closure = {**manifest['input_sha256'], **manifest['artifacts']}
            for filename in ('probe.tcl', 'view.spice', 'area.jsonl'):
                path = folder / filename
                if closure.get(str(path)) != sha(path):
                    raise ValueError('completed fixture file identity mismatch')
                pins[str(path)] = closure[str(path)]
        scripts_match = (x / 'probe.tcl').read_text().replace(str(x), '<CASE>') == (y / 'probe.tcl').read_text().replace(str(y), '<CASE>')
        sx, sy = signature((x / 'view.spice').read_text()), signature((y / 'view.spice').read_text())
        resistance_devices_ports_match = all(sx[i] == sy[i] for i in (0, 1, 3))
        rx, ry = events(x / 'area.jsonl'), events(y / 'area.jsonl')
        dx = [r for r in rx if r['kind'] == 'res_distribution_scale']
        dy = [r for r in ry if r['kind'] == 'res_distribution_scale']
        if len(dx) != 1 or len(dy) != 1:
            raise ValueError('one native area normalization per fixture required')
        total_x, total_y = [float.fromhex(r['before_hex']) for r in (dx[0], dy[0])]
        cap_total_match = dx[0]['source_hex'] == dy[0]['source_hex']
        raw_x = [r for r in rx if r['kind'] == 'raw_resistance_area']
        raw_y = [r for r in ry if r['kind'] == 'raw_resistance_area']
        raw_geometry_match = len(raw_x) == len(raw_y) and all(
            all(u[k] == v[k] for k in ('site', 'tile_box', 'support_box', 'weight_hex', 'split'))
            for u, v in zip(raw_x, raw_y))
        raw_value_checks = []
        changed_contributions = 0
        for u, v in zip(raw_x, raw_y):
            left, right = float.fromhex(u['native_added_hex']), float.fromhex(v['native_added_hex'])
            if corrected_case and u['site'] == 'ResCalcEastWest:0':
                raw_value_checks.append(left < 0 and right == -left)
                changed_contributions += 1
            else:
                raw_value_checks.append(left == right)
        required = [scripts_match, resistance_devices_ports_match, cap_total_match,
                    raw_geometry_match, all(raw_value_checks)]
        detail = dict(case=name, port_scope='localized' if before == baseline_local else 'broad',
                      electrical_protocol_matches=scripts_match,
                      resistance_device_and_port_inventories_match=resistance_devices_ports_match,
                      baseline_R_cards=sum(sx[3].values()), candidate_R_cards=sum(sy[3].values()),
                      raw_geometry_matches=raw_geometry_match, only_expected_raw_values_changed=all(raw_value_checks),
                      changed_single_breakpoint_contributions=changed_contributions,
                      native_total_capacitance_input_unchanged=cap_total_match,
                      baseline_total_area=total_x, candidate_total_area=total_y,
                      exact_exported_C_inventory_unchanged=sx[2] == sy[2])
        if corrected_case:
            expected = 4000 * 100 + 200 * 500
            # Fixture-only float32 accumulation allowance, scaled by the
            # observed update count. This is not a PLL accuracy criterion.
            ulp = 2.0 ** (math.floor(math.log2(expected)) - 23)
            operations = 1 + len(raw_y) + 3 * sum(r['kind'] == 'res_area_adjust' for r in ry) + sum(r['kind'] == 'res_node_merge' for r in ry)
            bound = ulp * operations
            area_matches = abs(total_y - expected) <= bound
            positive_raw = all(float.fromhex(r['native_added_hex']) >= 0 for r in raw_y)
            required.extend([changed_contributions == 1, area_matches, positive_raw])
            detail.update(geometric_union_area=expected, area_error=total_y - expected,
                          fixture_float32_roundoff_allowance=bound, corrected_area_matches_geometry=area_matches,
                          candidate_raw_contributions_nonnegative=positive_raw)
        else:
            required.extend([total_x == total_y, sx == sy, changed_contributions == 0])
            if before == baseline_broad:
                required.append(sum(sx[3].values()) > 0)
        detail['fixture_checks_passed'] = all(required)
        checks.extend(required)
        results.append(detail)
    verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'assessment.json', dict(input_sha256=pins, results=results,
                                          all_fixture_checks_passed=all(checks),
                                          broad_port_anomaly_fixed=False, coupling_duplication_fixed=False,
                                          distributed_wire_R_qualified=False, release_ready=False))
    if not all(checks):
        raise ValueError('area-sign fixture comparison failed; receipt retained')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    names = ('baseline_local', 'baseline_broad', 'candidate_local', 'candidate_broad', 'baseline_engine', 'engine', 'output')
    for name in names:
        p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    a = p.parse_args()
    run(*(getattr(a, name).resolve() for name in names))
