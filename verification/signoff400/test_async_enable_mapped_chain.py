"""Check actual mapped-chain validation against capture-bypass mutations."""
import copy
import json
from pathlib import Path
import unittest
from common_v3 import ROOT, verify
from synthesize_async_enable_candidate import capture_chain


class MappedCaptureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT/'build/signoff400/async_enable_candidate_mapping_909'
        assessment = json.loads((cls.folder/'assessment.json').read_text())
        verify(assessment['input_sha256'])
        verify(assessment['artifacts'])
        cls.modules = []
        for label in ('full', 'compact'):
            folder = cls.folder/label
            receipt = json.loads((folder/'assessment.json').read_text())
            verify(receipt['input_sha256'])
            verify(receipt['artifacts'])
            cls.modules.append(json.loads((folder/'mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore'])

    def test_actual_full_and_compact_mappings(self):
        for module in self.modules:
            with self.subTest():
                self.assertEqual(len(capture_chain(module)), 2)

    def test_bypass_second_stage_rejected(self):
        for original in self.modules:
            module = copy.deepcopy(original)
            chain = capture_chain(module)
            module['cells'][chain[1]['instance']]['connections']['D'] = module['ports']['PLL_ENABLE']['bits']
            with self.assertRaises(ValueError):
                capture_chain(module)

    def test_wrong_clock_rejected(self):
        for original in self.modules:
            module = copy.deepcopy(original)
            chain = capture_chain(module)
            module['cells'][chain[0]['instance']]['connections']['CLK'] = module['ports']['PLL_ENABLE']['bits']
            with self.assertRaises(ValueError):
                capture_chain(module)

    def test_missing_async_attribute_rejected(self):
        for original in self.modules:
            module = copy.deepcopy(original)
            del module['netnames']['enable_ref_pipe']['attributes']['ASYNC_REG']
            with self.assertRaises(ValueError):
                capture_chain(module)


if __name__ == '__main__':
    unittest.main()
