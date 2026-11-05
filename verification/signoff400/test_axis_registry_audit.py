import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import time
import unittest

from audit_native_axis_registry import audit_row, audit_stream
import test_native_axis_registry as producer_tests


class AxisRegistryAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        producer_tests.NativeAxisRegistry.setUpClass()

    @classmethod
    def tearDownClass(cls):
        producer_tests.NativeAxisRegistry.tearDownClass()

    def fixture(self, root):
        producer = producer_tests.NativeAxisRegistry()
        rows = [producer.row(1, 0, 10, state='full_tile_chain_positive_R'),
                producer.row(2, 2, 8), producer.row(3, 2, 8, material='ndiff'),
                producer.row(4, 2, 8, resistance='0'),
                producer.row(5, -1, 10, state='unsupported_creation_geometry')]
        p = producer.invoke(root, rows)
        self.assertEqual(p.returncode, 0, p.stderr)
        records = [json.loads(line) for line in (root/'native/axis_registry.jsonl').read_text().splitlines()]
        return rows, records

    def test_all_rows_and_exact_stream_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            totals, states, hashes = audit_stream(root/'chains.jsonl', root/'native/axis_registry.jsonl',
                                                  {'metal1': Fraction(125)}, time.monotonic()+30)
            self.assertEqual(totals['source_chains'], 5)
            self.assertEqual(totals['symbolic_end_resistors'], 2)
            self.assertEqual(len(states), 5)
            import hashlib
            self.assertEqual(hashes[0], hashlib.sha256((root/'chains.jsonl').read_bytes()).hexdigest())

    def test_numerical_identity_and_qualification_mutations_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, records = self.fixture(Path(temp))
            mutations = [lambda r: r.update(source_chain_byte_offset=1),
                         lambda r: r['native_voltage_knots'][0].__setitem__(1, '_rmesh_99_a'),
                         lambda r: r['end_stub_resistors'][0].update(nominal_resistance_milliohms_exact=['126', '1']),
                         lambda r: r.update(release_qualified=True),
                         lambda r: r['candidate_voltage_knots'].pop(),
                         lambda r: r.update(numeric_end_resistors_complete=False)]
            for mutate in mutations:
                record = copy.deepcopy(records[1])
                mutate(record)
                with self.assertRaises(ValueError):
                    audit_row(rows[1], record, 2, records[1]['source_chain_byte_offset'], {'metal1': Fraction(125)})
            record = copy.deepcopy(records[2])
            record['end_stub_resistors'][0]['nominal_resistance_milliohms_exact'] = ['1', '1']
            with self.assertRaises(ValueError):
                audit_row(rows[2], record, 3, records[2]['source_chain_byte_offset'], {'metal1': Fraction(125)})

    def test_truncation_extra_rows_and_deadline_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            target = root/'native/axis_registry.jsonl'
            original = target.read_bytes()
            for changed in (original.splitlines(keepends=True)[0], original+original):
                target.write_bytes(changed)
                with self.assertRaises(ValueError):
                    audit_stream(root/'chains.jsonl', target, {'metal1': Fraction(125)}, time.monotonic()+30)
            target.write_bytes(original)
            with self.assertRaisesRegex(ValueError, 'audit deadline'):
                audit_stream(root/'chains.jsonl', target, {'metal1': Fraction(125)}, time.monotonic()-1)
