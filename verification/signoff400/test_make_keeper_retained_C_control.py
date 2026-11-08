import tempfile
import unittest
from pathlib import Path
from make_keeper_retained_C_control import assemble, digest_cards
from audit_keeper_native_R_contraction import compare


class RetainedControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reference, self.native, self.control = [Path(self.tmp.name) / n for n in ('reference', 'native', 'control')]
        device = ' B 0 0 sky130_fd_pr__nfet_01v8 l=0.15u w=1u\n'
        self.reference.write_text('.subckt top A B\nX0 A' + device + 'C0 A 0 2f\nC1 A B 1f\nC2 unused 0 0\n.ends\n')
        self.native.write_text('.subckt top A B\nX0 A.n0' + device + 'R0 A A.n0 10\nC0 A 0 5f\nC1 A B 1f\n.ends\n')

    def test_control_preserves_literals_devices_R_and_charge(self):
        result = assemble(self.reference, self.native, self.control)
        self.assertEqual(result['original_C_cards_copied'], 3)
        self.assertEqual(digest_cards(self.reference, True), digest_cards(self.control, True))
        self.assertEqual(digest_cards(self.native, False), digest_cards(self.control, False))
        metrics = compare(self.reference.read_text(), self.control.read_text())
        self.assertTrue(metrics['exact_device_and_C_contraction_verified'])
        self.assertEqual(metrics['positive_wire_R_cards'], 1)

    def test_native_excess_is_detected_before_control(self):
        metrics = compare(self.reference.read_text(), self.native.read_text())
        self.assertFalse(metrics['exact_aggregated_C_match'])

    def test_nested_subcircuits_rejected(self):
        self.native.write_text(self.native.read_text() + '.subckt other X\n.ends\n')
        with self.assertRaisesRegex(ValueError, 'one flat'):
            assemble(self.reference, self.native, self.control)


if __name__ == '__main__':
    unittest.main()
