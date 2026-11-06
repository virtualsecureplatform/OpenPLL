"""Exercise routed capture auditing with actual-route bypass/fanout mutations."""
import copy
import json
import unittest
from common_v3 import ROOT, verify
from audit_async_enable_routed_capture import topology
from synthesize_async_enable_candidate import capture_chain


class RoutedCaptureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = ROOT/'build/signoff400'
        assessment = json.loads((root/'async_enable_routed_capture_917/assessment.json').read_text())
        verify(assessment['input_sha256'])
        verify(assessment['artifacts'])
        cls.module = json.loads((root/'async_enable_candidate_route_proof_915/proof/before_projection.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
        gold = json.loads((root/'async_enable_candidate_mapping_909/compact/mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
        cls.chain = capture_chain(gold)

    def test_actual_routed_chain(self):
        result = topology(self.module, self.chain)
        self.assertEqual(result['first_stage_functional_sinks'], [(result['cells'][1]['instance'], 'D')])

    def test_raw_input_bypass_rejected(self):
        module = copy.deepcopy(self.module)
        result = topology(module, self.chain)
        module['cells'][result['cells'][1]['instance']]['connections']['D'] = module['ports']['PLL_ENABLE']['bits']
        with self.assertRaises(ValueError):
            topology(module, self.chain)

    def test_extra_functional_first_stage_fanout_rejected(self):
        module = copy.deepcopy(self.module)
        result = topology(module, self.chain)
        first, second = [r['instance'] for r in result['cells']]
        other = next(c for n,c in module['cells'].items() if n not in (first,second) and c['type'].startswith('sky130_fd_sc_hs__dfrtp_'))
        other['connections']['D'] = module['cells'][first]['connections']['Q']
        with self.assertRaises(ValueError):
            topology(module, self.chain)

    def test_wrong_clock_rejected(self):
        module = copy.deepcopy(self.module)
        result = topology(module, self.chain)
        module['cells'][result['cells'][1]['instance']]['connections']['CLK'] = module['ports']['PLL_ENABLE']['bits']
        with self.assertRaises(ValueError):
            topology(module, self.chain)


if __name__ == '__main__':
    unittest.main()
