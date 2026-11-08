"""Follow observed unsimplified area states through merges and native scaling."""
import json
import math
import re
from collections import Counter
from fractions import Fraction
from audit_magic_resistance_area import f32


def audit(trace, res_ext):
    states = {}
    generations = Counter()
    outputs = Counter()
    input_nodes = []
    scaled_nodes = set()
    output_nodes = set()
    factor = None
    init_count = raw_count = merge_count = negative_raw = negative_final = 0
    adjust_count = 0
    adjust_sites = Counter()

    def number(r, name):
        value = float.fromhex(r[name + '_hex'])
        if not math.isfinite(value):
            raise ValueError('nonfinite resistance lineage')
        return value

    def state(node, expected, phase='area'):
        if node not in states or states[node] != (phase, expected):
            raise ValueError('node area/capacitance continuity failure')

    with trace.open() as stream:
        for line in stream:
            r = json.loads(line)
            if r['placement_qualified'] is not False:
                raise ValueError('diagnostic cannot qualify placement')
            kind, node = r['kind'], r['node_id']
            after = number(r, 'after')
            if kind == 'res_node_init':
                if after != 0:
                    raise ValueError('native node initialization must be zero')
                generations[node] += 1
                states[node] = ('area', 0.0)
                init_count += 1
            elif kind == 'raw_resistance_area':
                before, added = number(r, 'before'), number(r, 'native_added')
                state(node, before)
                if f32(f32(before) + f32(added)) != after:
                    raise ValueError('native raw float addition mismatch')
                states[node] = ('area', after)
                raw_count += 1
                negative_raw += added < 0
            elif kind == 'res_node_merge':
                before, source = number(r, 'before'), number(r, 'source')
                other = r['other_id']
                if node == other:
                    raise ValueError('self merge')
                state(node, before)
                state(other, source)
                if f32(before + source) != after:
                    raise ValueError('native merge float addition mismatch')
                states[node] = ('area', after)
                del states[other]
                merge_count += 1
            elif kind == 'res_area_adjust':
                before, added = number(r, 'before'), number(r, 'source')
                state(node, before)
                if f32(before + added) != after:
                    raise ValueError('native topological float adjustment mismatch')
                states[node] = ('area', after)
                adjust_count += 1
                adjust_sites[r['name']] += 1
            elif kind == 'res_distribution_input':
                state(node, after)
                if factor is not None or node in input_nodes:
                    raise ValueError('one distribution with unique inputs required')
                input_nodes.append(node)
            elif kind == 'res_distribution_scale':
                total, cap = number(r, 'before'), number(r, 'source')
                if not input_nodes or factor is not None:
                    raise ValueError('distribution inputs required before scale')
                accumulated = 0.0
                for key in input_nodes:
                    accumulated = f32(accumulated + states[key][1])
                if accumulated != total or total == 0 or f32(cap / total) != after:
                    raise ValueError('native area normalization mismatch')
                factor = after
            elif kind == 'res_distribution_output':
                before, scale = number(r, 'before'), number(r, 'scale')
                state(node, before)
                if node not in input_nodes or node in scaled_nodes or scale != factor:
                    raise ValueError('distribution output identity mismatch')
                if f32(before * scale) != after:
                    raise ValueError('native float scaling mismatch')
                states[node] = ('cap', after)
                scaled_nodes.add(node)
            elif kind == 'res_node_output':
                emitted, scale = number(r, 'source'), number(r, 'scale')
                state(node, after, 'cap')
                if node not in scaled_nodes or node in output_nodes or scale <= 0:
                    raise ValueError('invalid final node identity or scale')
                if f32(after / scale) != emitted or not isinstance(r['name'], str):
                    raise ValueError('native final export value mismatch')
                outputs[(r['name'], Fraction(format(emitted, '.6g')))] += 1
                output_nodes.add(node)
                negative_final += after < 0
            else:
                raise ValueError('unknown resistance lineage event')
    if not outputs or set(input_nodes) != scaled_nodes or scaled_nodes != output_nodes:
        raise ValueError('complete node distribution and export required')
    expected = Counter()
    with res_ext.open() as stream:
        for line in stream:
            if line.startswith('rnode '):
                m = re.match(r'rnode "([^\"]*)" \S+ (\S+)(?:\s|$)', line)
                if not m:
                    raise ValueError('unrecognized rnode export')
                name, cap = m.groups()
                expected[(name, Fraction(cap))] += 1
    return dict(node_initializations=init_count, pointer_reinitializations=sum(n - 1 for n in generations.values()),
                raw_area_updates=raw_count, observed_merges=merge_count,
                topological_area_adjustments=adjust_count,adjustment_sites=dict(adjust_sites),
                observed_node_state_continuity_verified=True, native_float_distribution_verified=True,
                negative_raw_additions=negative_raw, negative_final_nodes=negative_final,
                final_node_outputs=len(output_nodes), exported_rnode_records_match=expected == outputs,
                missing_rnode_records=sum((expected - outputs).values()),
                extra_rnode_records=sum((outputs - expected).values()),
                unexported_nonzero_area_states=sum(phase == 'area' and v != 0 for phase, v in states.values()),
                geometric_merge_basis_qualified=False, capacitance_placement_qualified=False,
                distributed_wire_R_qualified=False, release_ready=False)
