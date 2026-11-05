"""Serial/parallel equivalence and corruption checks for aligned C shards."""
from concurrent.futures import ProcessPoolExecutor
import json
import math
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'timing400'))
from compile_local_C_operators_v5 import compile_trace as serial
from compile_local_C_operators_v6 import compile_trace
from parallel_C_trace_ranges import partition, metadata, ranged_owned_blocks, lower_bound, native_offsets
from compile_capacitance_parallel import merge


def fixture(trace):
    kernels, owners = ['BEGIN "test"'], ['BEGIN "test"']
    surface = ['BEGIN "test"', 'TYPE 2 "metal"', 'TYPE 3 "contact"', 'PLANE 1 "metal"']
    native = ['OPENPLL_BEGIN']
    events = 0
    owner_count = 0
    kinds = ['AREA', 'EDGE', 'OVERLAP', 'OVERLAP_SELF', 'ROUNDING', 'SIDEWALL',
             'FRINGE_HALO', 'FRINGE_SELF', 'BLOCKED_FRINGE']*3
    for k, kind in enumerate(kinds, 1):
        self_pair = kind.endswith('_SELF')
        actual = {'OVERLAP_SELF': 'OVERLAP', 'FRINGE_SELF': 'FRINGE_HALO'}.get(kind, kind)
        direction = 4 if actual == 'FRINGE_HALO' else 1
        kernels.append(f'KERNEL {k} {actual} {direction}')
        def rect(tag, box):
            kernels.append(f'RECT {k} {tag} 0 0 0 '+ ' '.join(map(str, box)))
        def value(tag, values):
            kernels.append(f'VALUE {k} {tag} 0 '+ ' '.join(map(str, values+[0]*(8-len(values)))))
        pair = actual in ('OVERLAP', 'SIDEWALL', 'FRINGE_HALO') and not self_pair
        if actual == 'AREA':
            rect('BASE_A', [0, 0, 2, 3]); value('AREA_DENSITY', [6, 2]); delta = 12
        elif actual == 'EDGE':
            rect('BASE_A', [0, 0, 0, 3]); value('EDGE_DENSITY', [3, 2]); delta = 6
        elif actual == 'OVERLAP':
            rect('BASE_A', [0, 0, 2, 3]); value('OVERLAP_BASE', [0, 1, 2])
            value('OVERLAP_REMAINING', [6]); delta = -6 if self_pair else 12
        elif actual == 'SIDEWALL':
            rect('BASE_A', [0, 0, 0, 3]); rect('BASE_B', [2, 0, 2, 3])
            value('SIDEWALL_BASE', [3, 2]); value('SIDEWALL_RULE', [4, 2]); delta = 3
        elif actual == 'FRINGE_HALO':
            rect('BASE_A', [0, 0, 0, 3]); rect('BASE_B', [1, 0, 2, 3])
            amount = 2*3*.6366*(math.atan(2)-math.atan(1))
            value('FRINGE_BASE', [3, 0, 0, 1, 0, amount/6, 0])
            value('HALO_RULE', [2]); value('HALO_RULE_REMAINING', [0, 0, int(not self_pair)])
            value('PAIR_PHYSICAL', [amount]); value('GROUND_PHYSICAL', [0])
            delta = 0 if self_pair else amount
        elif actual == 'BLOCKED_FRINGE':
            rect('BASE_A', [0, 0, 0, 3]); value('BLOCKED_BASE', [0, 0, 0, .5, 2, 3]); delta = -3
        else:
            delta = 1e-12
        if actual in ('OVERLAP', 'SIDEWALL', 'FRINGE_HALO'):
            b = 'a' if self_pair else 'b'
            owners.append(f'OWNER {k} a {b} 1 3 3 1 2 2 {int(self_pair)}')
            owner_count += 1
        if kind == 'OVERLAP_SELF' and k % 2:
            continue  # Omitted native pair still restores finite-R self energy.
        if kind == 'OVERLAP':
            events += 1
            kernels.append(f'EVENT {events} G {k} TEST_OVERLAP_GROUND')
            surface.append(f'SURFACE {events} G 1 3 2 -1 -1 -1')
            native.append('OPENPLL_G a -6')
        events += 1
        pg = 'P' if pair else 'G'
        kernels.append(f'EVENT {events} {pg} {k} TEST_{actual}')
        if actual == 'ROUNDING':
            surface.append(f'SURFACE {events} G -1 -1 -1 -1 -1 -1')
        else:
            surface.append(f'SURFACE {events} {pg} 1 3 2 '+('1 2 2' if pair else '-1 -1 -1'))
        native.append(f'OPENPLL_P a b {delta}' if pair else f'OPENPLL_G a {delta}')
    kernels.append(f'END {events} {len(kinds)}')
    owners.append(f'END {owner_count} {len(kinds)}')
    surface.append(f'END {events}')
    native += ['OPENPLL_ID a "NET_A" 0', 'OPENPLL_ID b "NET_B" 0', 'OPENPLL_ID sub "VGND" 1', 'OPENPLL_END']
    for name, rows in [('kernels', kernels), ('owners', owners), ('surfaces', surface), ('contributions', native)]:
        (trace/f'{name}.log').write_text('\n'.join(rows)+'\n')
    (trace/'node_ids.json').write_text(json.dumps(dict(a='NET_A', b='NET_B', sub='@SUBSTRATE')))


def normalized_rows(path, fieldmap):
    result = []
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            row[1], row[2] = fieldmap[row[1]], fieldmap[row[2]]
            result.append(row)
    return result


class ParallelCapacitance(unittest.TestCase):
    def test_large_sparse_search_and_chunk_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'records'
            with path.open('wb') as stream:
                stream.write(b'BEGIN test\n')
                offsets = {}
                for k in range(1, 70001):
                    offsets[k*3] = stream.tell()
                    stream.write(f'OWNER {k*3} a b 1 2 3 4 5 6 0\n'.encode())
                end = stream.tell(); stream.write(b'END 70000 210000\n')
            for target in (1, 3, 4, 99999, 100000, 209999, 210000, 210001):
                expected = next((v for k, v in offsets.items() if k >= target), end)
                self.assertEqual(lower_bound(path, b'OWNER', target), expected)
            path.write_bytes(b'header\n'+b'OPENPLL_G a 1\nOPENPLL_P a b 2\n'*400000+b'OPENPLL_END\n')
            found, count = native_offsets(path, [0, 400000, 799999, 800000],
                                         time.clock_gettime(time.CLOCK_BOOTTIME)+30)
            self.assertEqual(count, 800000)
            with path.open('rb') as stream:
                for rank in (0, 400000, 799999):
                    stream.seek(found[rank])
                    self.assertTrue(stream.readline().startswith(b'OPENPLL_'))
            self.assertEqual(found[800000], path.stat().st_size)

    def test_four_process_equivalence_and_bad_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); trace = root/'trace'; trace.mkdir(); fixture(trace)
            deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+60
            baseline = root/'serial'; serial(trace, baseline, deadline)
            specs = partition(trace, 4, deadline)
            out = root/'parallel'; out.mkdir()
            meta = out/'metadata.json'; meta.write_text(json.dumps(metadata(trace)))
            with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn')) as pool:
                futures = [pool.submit(compile_trace, trace, out/f'worker_{i}', deadline, None, spec, meta)
                           for i, spec in enumerate(specs)]
                receipts = [f.result() for f in futures]
            merged = merge(out, receipts)
            expected = json.loads((baseline/'assessment.json').read_text())
            self.assertEqual(merged['counts'], expected['counts'])
            base_fields = json.loads((baseline/'fields.json').read_text())
            merged_fields = json.loads((out/'fields.json').read_text())
            rows = []
            for i in range(4):
                local = json.loads((out/f'worker_{i}/fields.json').read_text())
                mapping = json.loads((out/f'worker_{i}_field_map.json').read_text())
                self.assertEqual([merged_fields[n] for n in mapping], local)
                rows.extend(normalized_rows(out/f'worker_{i}/operators.jsonl', local))
            self.assertEqual(rows, normalized_rows(baseline/'operators.jsonl', base_fields))
            def ledger(path, fields):
                return {tuple(sorted((tuple(fields[a]), tuple(fields[b])))): values
                        for a, b, *values in json.loads(path.read_text())}
            before = ledger(baseline/'collapsed_matrix_ledger.json', base_fields)
            after = ledger(out/'collapsed_matrix_ledger.json', merged_fields)
            self.assertEqual(before.keys(), after.keys())
            for key in before:
                for a, b in zip(before[key], after[key]):
                    self.assertAlmostEqual(a, b, places=10)
            bad = dict(specs[0], event_end=specs[0]['event_end']+1)
            with self.assertRaises(AssertionError):
                list(ranged_owned_blocks(trace, deadline, bad))
            text = (trace/'surfaces.log').read_text().replace('SURFACE 1 ', 'SURFACE 2 ', 1)
            (trace/'surfaces.log').write_text(text)
            with self.assertRaises(AssertionError):
                compile_trace(trace, root/'corrupt', deadline, None, specs[0], meta)


if __name__ == '__main__':
    unittest.main()
