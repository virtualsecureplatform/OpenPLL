"""Cross-check actual native input budgets and reject incomplete path reports."""
import json
import re
import unittest
from common_v3 import ROOT, verify
from measure_selected_enable_input_timing_v2 import paths_from_report


class EnableTimingControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = ROOT/'build/signoff400/selected_enable_input_timing_937'
        assessment = json.loads((folder/'assessment.json').read_text())
        verify(assessment['input_sha256']); verify(assessment['artifacts'])
        cls.targets = json.loads((folder/'inputs.json').read_text())['REFCLK_destination_registers']
        cls.text = (folder/'tt_slew0.1/paths.log').read_text()

    def test_budgets_independently_match_arrival_and_required_times(self):
        records = paths_from_report(self.text,self.targets)
        self.assertEqual(len(records),152)
        for record,block in zip(records,self.text.split('Startpoint: ')[1:]):
            number = r'([-+0-9.eE]+)'
            arrival = float(re.search(number+r'\s+data arrival time',block)[1])
            required = float(re.search(number+r'\s+data required time',block)[1])
            expected = 40+arrival-required if record['kind'] == 'max' else required-arrival
            actual = record['required_external_setup_ns'] if record['kind'] == 'max' else record['required_external_hold_ns']
            # Independently printed native float32 times can differ by a few fs.
            self.assertAlmostEqual(actual,expected,delta=.000005)

    def test_missing_capture_path_rejected(self):
        blocks = self.text.split('Startpoint: ')
        with self.assertRaises(ValueError):
            paths_from_report(blocks[0]+'Startpoint: '+'Startpoint: '.join(blocks[2:]),self.targets)

    def test_duplicate_capture_path_rejected(self):
        with self.assertRaises(ValueError):
            paths_from_report(self.text+'Startpoint: '+self.text.split('Startpoint: ')[-1],self.targets)

    def test_wrong_clock_rejected(self):
        with self.assertRaises(ValueError):
            paths_from_report(self.text.replace('clock REFCLK (rise edge)','clock FINECLK (rise edge)',1),self.targets)


if __name__ == '__main__':
    unittest.main()
