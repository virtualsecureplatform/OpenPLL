#!/usr/bin/env python3
"""Fault-injection checks against actual elaborated load-bank candidates."""
import copy
import json
from pathlib import Path
import unittest

from check_dco_c1_fine_load import check
from prepare_dco_c1_fine_load import BASE, names
from run_dco_c1_fine_load import viable
from screen_dco_c1_fine_load_pvt import find_bracket

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/timing450/dco_c1_fine_load_001'


class Checks(unittest.TestCase):
    def setUp(self):
        top, _ = names(160)
        self.base = json.loads((OUT/(BASE+'.json')).read_text())['modules'][BASE]
        self.candidate = json.loads((OUT/(top+'.json')).read_text())['modules'][top]

    def test_actual_candidates(self):
        for count in (144,160,192):
            top, _ = names(count)
            candidate = json.loads((OUT/(top+'.json')).read_text())['modules'][top]
            self.assertTrue(check(self.base,candidate,count)['passed'])

    def reject(self, change):
        candidate = copy.deepcopy(self.candidate)
        change(candidate)
        with self.assertRaises((AssertionError, KeyError)):
            check(self.base,candidate,160)

    def test_wrong_turn(self):
        self.reject(lambda m:m['cells']['gen_coarse1_fine_load[0].load']['connections'].update(A=[m['netnames']['mirror_turn_n']['bits'][0]]))

    def test_wrong_enable(self):
        self.reject(lambda m:m['cells']['gen_coarse1_fine_load[0].load']['connections'].update(TE=[m['ports']['DCO_THERM']['bits'][1]]))

    def test_aliased_dummy(self):
        self.reject(lambda m:m['cells']['gen_coarse1_fine_load[0].load']['connections'].update(Z=[m['netnames']['coarse1_fine_dummy']['bits'][1]]))

    def test_original_driver_changed(self):
        self.reject(lambda m:m['cells']['osc_gate']['connections'].update(B=[m['ports']['DCO_THERM']['bits'][0]]))

    def test_missing_original_cell(self):
        self.reject(lambda m:m['cells'].pop('out_buf'))

    def test_extra_cell(self):
        self.reject(lambda m:m['cells'].update(unexpected=copy.deepcopy(m['cells']['out_buf'])))

    def test_range_requires_margins_and_order(self):
        self.assertTrue(viable([390,425,460]))
        for bad in ([391,425,460], [390,425,459], [390,390,460],
                    [390,470,460], [], [390,460]):
            self.assertFalse(viable(bad))

    def test_adaptive_search_requires_measured_bracket(self):
        calls = []
        def sample(coarse):
            calls.append(coarse)
            return (950/(coarse+1),1050/(coarse+1))
        result = find_bracket(100,sample)
        self.assertTrue(result['passed'])
        self.assertIn(result['coarse'],calls)
        self.assertLessEqual(result['endpoints_mhz'][0],100)
        self.assertGreaterEqual(result['endpoints_mhz'][1],100)
        self.assertEqual(len(calls),len(set(calls)))

    def test_adaptive_gap_fails_closed(self):
        result = find_bracket(450,lambda c:(1000/(c+1),1010/(c+1)))
        self.assertFalse(result['passed'])
        self.assertFalse(result['global_unreachability_proven'])

    def test_adaptive_native_nonpass_and_reversed_range(self):
        for sample in (lambda c:None,lambda c:[500,400]):
            result = find_bracket(450,sample)
            self.assertFalse(result['passed'])
            self.assertEqual(len(result['trace']),1)


if __name__ == '__main__':
    unittest.main()
