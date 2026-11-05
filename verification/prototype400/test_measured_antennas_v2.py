"""Select actual violating pins, retaining safe Tcl quoting for native names."""
import unittest
from repair_measured_antennas_v2 import violation_targets, repair_tcl


class MeasuredAntennasV2(unittest.TestCase):
    def test_only_violating_pins_are_selected_and_multiple_layers_deduplicate(self):
        text='''Net: $net[3]
  Pin: $cell/with/hierarchy/A (gate)
    value (VIOLATED)
    other (VIOLATED)
  Pin: harmless/B (gate)
    value (MET)
Net: PLLOUT
  Pin: clkbuf/A (buffer)
    value (VIOLATED)
'''
        targets=violation_targets(text)
        self.assertEqual(targets,[('$net[3]','$cell/with/hierarchy','A'),('PLLOUT','clkbuf','A')])
        script=repair_tcl(targets)
        self.assertIn('findNet {$net[3]}',script)
        self.assertIn('findInst {$cell/with/hierarchy}',script)
        self.assertIn('measured_local_diode_1',script)
        self.assertEqual(script.count('global_route -start_incremental'),1)
        self.assertEqual(script.count('global_route -end_incremental'),1)

    def test_source_namespace_and_collision_guard(self):
        script=repair_tcl([('N','sink','A')], 'measured_diode_123abc')
        self.assertIn('findInst measured_diode_123abc_0',script)
        self.assertIn('diode instance already exists',script)
        self.assertNotIn('@PREFIX@',script)
        for prefix in ('x;exit', 'x}evil', '9bad', ''):
            with self.assertRaises(ValueError):repair_tcl([('N','sink','A')],prefix)

    def test_missing_context_and_unsafe_names_are_rejected(self):
        for text in ('value (VIOLATED)', 'Net: X\nvalue (VIOLATED)', 'Net: X\n Pin: no_terminal (gate)'):
            with self.assertRaises(ValueError):
                violation_targets(text)
        for name in ('bad}name','bad\\name','bad\nname'):
            with self.assertRaises(ValueError):
                repair_tcl([(name,'sink','A')])


if __name__=='__main__':
    unittest.main()
