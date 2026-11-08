"""Validate ordered numerical ground updates and native exported node records.

This validates a diagnostic ledger, not spatial capacitance placement.
"""
import json
import math
import re
from collections import Counter
from fractions import Fraction
from audit_magic_coupling_geometry_trace import lines


def finite_hex(value):
    result = float.fromhex(value)
    if not math.isfinite(result):
        raise ValueError('nonfinite ground ledger value')
    return result


def audit(trace, ext):
    states = {}
    epochs = set()
    sites = Counter()
    outputs = Counter()
    resets = updates = clamps = substrate = 0
    output_ids = set()
    ignored = {'node_name', 'overlap', 'sidewall', 'sideoverlap_halo', 'sideoverlap_legacy'}
    for line in lines(trace):
        r = json.loads(line)
        prefix = (r['cell'], r['epoch'])
        epochs.add(prefix)
        kind = r['kind']
        if kind in ignored:
            continue
        key = (*prefix, r['node_id'])
        if kind == 'ground_update':
            if key in output_ids:
                raise ValueError('ground mutation after node output')
            after = finite_hex(r['after_hex'])
            if r['has_before'] is True:
                before = finite_hex(r['before_hex'])
                if key not in states or states[key] != before:
                    raise ValueError('ground update continuity failure')
                updates += 1
            elif r['has_before'] is False:
                resets += 1
            else:
                raise ValueError('explicit before-value presence required')
            states[key] = after
            sites[r['site']] += 1
        elif kind == 'ground_output':
            native = finite_hex(r['native_hex'])
            scale = finite_hex(r['scale_hex'])
            emitted = finite_hex(r['emitted_hex'])
            if scale <= 0 or key not in states or states[key] != native:
                raise ValueError('ground output differs from recorded state')
            if key in output_ids:
                raise ValueError('duplicate node output')
            output_ids.add(key)
            if r['substrate'] is True:
                expected = 0.0
                substrate += 1
                tag = 'substrate'
            elif r['substrate'] is False:
                expected = max(0.0, native / scale)
                clamps += native < 0
                tag = 'node'
            else:
                raise ValueError('explicit substrate flag required')
            if emitted != expected:
                raise ValueError('native ground output clamp or scale mismatch')
            outputs[(tag, r['name'], Fraction(format(emitted, '.6g')))] += 1
        else:
            raise ValueError('unknown lifecycle event')
    if len(epochs) != 1 or not outputs:
        raise ValueError('one completed extraction epoch with node outputs required')
    exported = Counter()
    for line in lines(ext):
        if line.startswith('use '):
            raise ValueError('flat extraction required')
        if line.startswith(('node ', 'substrate ')):
            m = re.match(r'(node|substrate) "([^\"]*)" \S+ (\S+)(?:\s|$)', line)
            if not m:
                raise ValueError('unrecognized ground node record')
            tag, name, value = m.groups()
            exported[(tag, name, Fraction(value))] += 1
    return dict(ground_updates=updates, ground_resets=resets,
                mutation_sites_observed=dict(sites), ground_output_records=sum(outputs.values()),
                substrate_output_records=substrate, negative_export_clamps=clamps,
                native_ground_state_continuity_verified=True,
                exported_ground_records_match=outputs == exported,
                missing_exported_records=sum((exported - outputs).values()),
                extra_reconstructed_records=sum((outputs - exported).values()),
                spatial_ground_placement_qualified=False, distributed_wire_R_qualified=False,
                release_ready=False)
