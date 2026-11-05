"""Independent Python/native comparisons and failure controls for charge compilation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from common import ROOT, save
from compiled_charge import build, compile_shard, execute

sys.path.append(str(ROOT / 'verification/prototype400'))
sys.path.append(str(ROOT / 'verification/timing400'))
from test_parallel_capacitance import fixture, normalized_rows
from compile_local_C_operators_v6 import compile_trace
from parallel_C_trace_ranges import partition, metadata
from parallel_C_trace_ranges import native_offsets
from compiled_partition import partition as native_partition


class CompiledCharge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = build(Path(cls.temp.name) / 'build')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def prepare(self, root):
        trace = root / 'trace'
        trace.mkdir()
        fixture(trace)
        native = trace / 'contributions.log'
        native.write_text(native.read_text().replace('OPENPLL_G a 12\n',
                          'OPENPLL_G a 12 tile_area box 0 0 2 3\n'))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 60
        meta = root / 'metadata.json'
        execute([self.binary, 'metadata', trace, meta, deadline], root / 'meta.log', deadline)
        self.assertEqual(json.loads(meta.read_text()), json.loads(json.dumps(metadata(trace))))
        return trace, deadline, meta

    def test_all_kernels_shards_and_worker_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace, deadline, meta = self.prepare(root)
            for workers in (1, 4, 8):
                for i, span in enumerate(partition(trace, workers, deadline)):
                    python_out, native_out = root / f'py{workers}_{i}', root / f'cpp{workers}_{i}'
                    expected = compile_trace(trace, python_out, deadline, None, span, meta)
                    actual = compile_shard(self.binary, trace, native_out, deadline, span, meta)
                    self.assertEqual(actual['counts'], expected['counts'])
                    self.assertEqual(actual['components'], expected['components'])
                    fields = json.loads((python_out / 'fields.json').read_text())
                    self.assertEqual(json.loads((native_out / 'fields.json').read_text()), fields)
                    self.assertEqual(normalized_rows(python_out / 'operators.jsonl', fields),
                                     normalized_rows(native_out / 'operators.jsonl', fields))
                    self.assertEqual(json.loads((python_out / 'collapsed_matrix_ledger.json').read_text()),
                                     json.loads((native_out / 'collapsed_matrix_ledger.json').read_text()))
                    self.assertFalse(actual['runtime_model_eligible'])

    def test_native_empty_self_rule_collections(self):
        # Retained native kernel 50400955 has SIDEWALL_BASE but no rules.
        # Python's defaultdict treats this as zero energy, not malformed input.
        for kind in ('SIDEWALL', 'FRINGE_HALO'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                trace, deadline, meta = self.prepare(root)
                kernels = trace / 'kernels.log'
                rows = kernels.read_text().splitlines()
                end = rows.pop().split()
                kid = int(end[2]) + 1
                rows += [f'KERNEL {kid} {kind} 2',
                         f'RECT {kid} BASE_A 0 0 0 48435 37766 48444 37766',
                         f'RECT {kid} BASE_B 0 0 0 48435 38214 48444 38214']
                if kind == 'SIDEWALL':
                    rows += [f'VALUE {kid} SIDEWALL_BASE 0 9 448 9 0 0 0 0 0']
                else:
                    rows += [f'VALUE {kid} FRINGE_BASE 0 9 0 0 1 0 0 0 0']
                rows += [f'END {end[1]} {kid}']
                kernels.write_text('\n'.join(rows) + '\n')
                owners = trace / 'owners.log'
                rows = owners.read_text().splitlines()
                end = rows.pop().split()
                rows += [f'OWNER {kid} a a 1 2 2 1 2 2 1',
                         f'END {int(end[1]) + 1} {kid}']
                owners.write_text('\n'.join(rows) + '\n')
                span = partition(trace, 1, deadline)[0]
                pyout, cppout = root / 'python', root / 'compiled'
                expected = compile_trace(trace, pyout, deadline, None, span, meta)
                actual = compile_shard(self.binary, trace, cppout, deadline, span, meta)
                self.assertEqual(actual['counts'], expected['counts'])
                for name in ('operators.jsonl', 'fields.json', 'collapsed_matrix_ledger.json'):
                    if name.endswith('jsonl'):
                        self.assertEqual([json.loads(r) for r in (cppout / name).read_text().splitlines()],
                                         [json.loads(r) for r in (pyout / name).read_text().splitlines()])
                    else:
                        self.assertEqual(json.loads((cppout / name).read_text()),
                                         json.loads((pyout / name).read_text()))

    def test_corruption_truncation_deadline_and_fresh_output(self):
        for fault in ('surface', 'native', 'owner', 'range', 'truncated', 'nonfinite', 'missing_owner'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                trace, deadline, meta = self.prepare(root)
                span = partition(trace, 1, deadline)[0]
                if fault == 'range':
                    span['event_end'] += 1
                else:
                    name = dict(surface='surfaces', native='contributions', owner='owners',
                                truncated='kernels', nonfinite='kernels', missing_owner='owners')[fault]
                    p = trace / (name + '.log')
                    data = p.read_text()
                    if fault == 'surface': data = data.replace('SURFACE 1 ', 'SURFACE 2 ', 1)
                    elif fault == 'native': data = data.replace('OPENPLL_P a b ', 'OPENPLL_P b a ', 1)
                    elif fault == 'owner': data = data.replace(' 0\n', ' 2\n', 1)
                    elif fault == 'nonfinite': data = data.replace(' 6 2 ', ' nan 2 ', 1)
                    elif fault == 'missing_owner': data = data.replace('OWNER ', 'WRONG ', 1)
                    else: data = data[:-20]
                    p.write_text(data)
                with self.assertRaises(RuntimeError):
                    compile_shard(self.binary, trace, root / 'bad', deadline, span, meta)
                self.assertFalse((root / 'bad/assessment.json').exists())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace, deadline, meta = self.prepare(root)
            span = partition(trace, 1, deadline)[0]
            out = root / 'completed'
            compile_shard(self.binary, trace, out, deadline, span, meta)
            with self.assertRaises(FileExistsError):
                compile_shard(self.binary, trace, out, deadline, span, meta)
            with self.assertRaises(TimeoutError):
                compile_shard(self.binary, trace, root / 'expired', 0, span, meta)

    def test_signed_overlap_shield_is_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace, deadline, meta = self.prepare(root)
            kernels = trace/'kernels.log'
            text = kernels.read_text().replace('VALUE 3 OVERLAP_REMAINING 0 6 ',
                    'RECT 3 AREA_SHIELD 0 0 0 0 0 1 1\nVALUE 3 OVERLAP_REMAINING 0 5 ')
            kernels.write_text(text)
            native = trace/'contributions.log'
            native.write_text(native.read_text().replace('OPENPLL_G a -6\n','OPENPLL_G a -5\n',1)
                              .replace('OPENPLL_P a b 12\n','OPENPLL_P a b 10\n',1))
            span = partition(trace,1,deadline)[0]
            expected = compile_trace(trace,root/'reference',deadline,None,span,meta)
            actual = compile_shard(self.binary,trace,root/'native',deadline,span,meta)
            self.assertEqual(actual['counts'],expected['counts'])
            fields = json.loads((root/'reference/fields.json').read_text())
            rows = normalized_rows(root/'native/operators.jsonl',fields)
            self.assertEqual(rows,normalized_rows(root/'reference/operators.jsonl',fields))
            self.assertTrue(any(r[0]=='A' and r[-1]<0 for r in rows if r[3]==4))

    def test_compiled_index_matches_sparse_native_ranks_and_partition(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            trace,deadline,meta=self.prepare(root)
            for workers in (1,4,8):
                group=root/f'index{workers}';group.mkdir()
                self.assertEqual(native_partition(trace,workers,deadline,self.binary,group,index_workers=workers),
                                 partition(trace,workers,deadline))
            path=root/'large_native.log'
            path.write_bytes(b'OPENPLL_BEGIN\n'+b'OPENPLL_G a 1\nOPENPLL_P a b 2\n'*400000+b'OPENPLL_END\n')
            ranks=[0,1,399999,400000,799999,800000]
            expected,total=native_offsets(path,ranks,deadline)
            for workers in (1,8,32):
                output=root/f'ranks{workers}.json';config=root/f'config{workers}.json'
                save(config,dict(path=str(path),output=str(output),workers=workers,ranks=ranks,deadline_uptime=deadline))
                execute([self.binary,'index',config],root/f'ranks{workers}.log',deadline)
                actual=json.loads(output.read_text())
                self.assertEqual(actual['events'],total)
                self.assertEqual({int(k):v for k,v in actual['offsets'].items()},expected)


if __name__ == '__main__':
    unittest.main()
