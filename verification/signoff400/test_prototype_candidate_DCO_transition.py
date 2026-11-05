import unittest
from run_prototype_candidate_DCO_transition import transition_deck

class CandidateTransition(unittest.TestCase):
    def baseline(self):
        return '\n'.join([f'VCTRL{i:03d} DCO_THERM[{i}] 0 {{VDD}}' for i in range(255)]+[
            'VRESET RESET_N 0 PULSE(0 {VDD} 5.0n 50p 50p 40.0n 80.0n)',
            '.tran 10.0p 40.0n 0 10.0p', '.include "unchanged.spice"'])

    def test_inverted_thermometer_one_bit_and_extreme_hazard(self):
        source = self.baseline()
        result = transition_deck(source, 127, 128)
        self.assertIn('VCTRL127 DCO_THERM[127] 0 PWL(0 {VDD} 19.9n {VDD} 20.1n 0)', result)
        self.assertIn('VCTRL126 DCO_THERM[126] 0 PWL(0 0 19.9n 0 20.1n 0)', result)
        self.assertEqual(source.splitlines()[-3:], result.splitlines()[-3:])
        hazard = transition_deck(source,127,128,0)
        self.assertIn('VCTRL126 DCO_THERM[126] 0 PWL(0 0 19.8n 0 20n {VDD} 20.2n {VDD} 20.4n 0)',hazard)

    def test_reject_missing_or_duplicate_sources_and_changed_reset(self):
        source = self.baseline()
        for bad in (source.replace('VCTRL254','VCTRL253'), source.replace('40.0n 80.0n','20.0n 40.0n')):
            with self.assertRaises(ValueError): transition_deck(bad,127,128)
        with self.assertRaises(ValueError): transition_deck(source,127,128,1)

if __name__ == '__main__': unittest.main()
