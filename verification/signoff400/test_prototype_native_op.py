import unittest
from prototype_native_op import reset_voltages, dc_body, read_operating_point


class OperatingPointControl(unittest.TestCase):
    def test_only_explicit_C_is_opened_and_all_devices_R_survive(self):
        source = '.subckt Top A B\nXflat0 A B 0 0 model\nRparentWire0 A B 2\nCflat0 A 0 -1e-15\nCkron0 A B 1e-15\n.ends Top\n'
        body, count = dc_body(source)
        self.assertEqual(count, 2)
        self.assertIn('Xflat0 A B 0 0 model', body)
        self.assertIn('RparentWire0 A B 2', body)
        self.assertNotIn('Cflat0', body)

    def test_all_reset_inputs_are_defined_without_clamping_outputs(self):
        values = reset_voltages()
        self.assertEqual(len(values), 35)
        self.assertEqual(values['RESET_N'], 0.)
        self.assertEqual(values['STARTUP_FINE[1]'], 1.8)
        self.assertNotIn('PLLOUT', values)

    def test_real_complete_native_point_and_failures(self):
        raw = 'Plotname: Operating Point\nFlags: real\nNo. Variables: 2\nNo. Points: 1\nVariables:\n0 v(vpwr) voltage\n1 v(pllout) voltage\nValues:\n0 1.8\n0\n'
        self.assertEqual(read_operating_point(raw), {'v(vpwr)': 1.8, 'v(pllout)': 0.})
        for wrong in (raw.replace('1.8', 'nan'), raw.replace('No. Points: 1', 'No. Points: 2'),
                      raw.replace('0 1.8\n0', '0 1.8'), raw.replace('Flags: real', 'Flags: complex')):
            with self.assertRaises(ValueError):
                read_operating_point(wrong)


if __name__ == '__main__': unittest.main()
