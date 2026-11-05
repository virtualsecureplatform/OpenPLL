import unittest
from measure_selected_retimer_clock_paths import carrier_pair,interpolate


class RetimerClockPathTest(unittest.TestCase):
    def test_ordered_edges_measure_transport_without_modulo_pairing(self):
        root=[184,186.5,189,191.5];clock=[t+.25 for t in root]
        r,c,report=carrier_pair(root,clock)
        self.assertEqual(r,root);self.assertEqual(c,clock)
        self.assertEqual(report['observed_transport_interval_ps'],[250,250])

    def test_lost_clock_and_whole_cycle_ambiguity_are_rejected(self):
        root=[184,186.5,189,191.5]
        with self.assertRaises(ValueError):carrier_pair(root,[184.25,189.25,191.75])
        with self.assertRaises(ValueError):carrier_pair(root,[t+2.75 for t in root])

    def test_measured_voltage_interpolation_never_extrapolates(self):
        self.assertAlmostEqual(interpolate([(0,0),(2e-9,1.8)],1),.9)
        with self.assertRaisesRegex(ValueError,'extrapolation'):interpolate([(0,0),(2e-9,1.8)],3)


if __name__=='__main__':unittest.main()
