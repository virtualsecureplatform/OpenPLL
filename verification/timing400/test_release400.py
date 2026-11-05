import copy
import json
from pathlib import Path
import unittest

from run_dco_qualification import REQUIREMENTS, ROOT, validate_spec, occupancy, covered, seed_from_bracket, find_bracket
from prepare_functional_matrix import cases_for


class Release400Checks(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(REQUIREMENTS.read_text())
        self.targets = json.loads((ROOT/'sky130/release_400mhz_targets.json').read_text())

    def test_matrix_and_all_directed_transitions(self):
        cases = cases_for(self.spec,self.targets)
        self.assertEqual(len(cases),60)
        for corner in self.spec['corners']:
            for temp in self.spec['temperatures_c']:
                subset = [c for c in cases if c['corner']==corner and c['temperature_c']==temp]
                self.assertEqual(len(subset),4)
                transitions = {(old,c['mode_mhz']) for c in subset for old in c['incoming_mode_changes_mhz']}
                self.assertEqual(len(transitions),12)
        self.assertTrue(all(not c['execution_eligible'] and not c['passed'] for c in cases))

    def test_stale_five_mode_spec_rejected(self):
        self.spec['modes_mhz'].append(450)
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_stale_case_count_rejected(self):
        self.spec['release_scope']['required_mode_pvt_combinations']=75
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_off_nominal_rejected(self):
        self.spec['voltages']=[1.62,1.8,1.95]
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_wrong_divider_rejected(self):
        self.targets['targets']['400']['ndiv']=18
        with self.assertRaises(ValueError):cases_for(self.spec,self.targets)

    def test_stale_target_preset_rejected(self):
        self.targets['targets']['450']={'ndiv':18}
        with self.assertRaises(ValueError):cases_for(self.spec,self.targets)

    def test_slots_count_preparation_and_external_jobs(self):
        external=[{'ppid':20},{'ppid':20},{'ppid':20}]
        self.assertEqual(occupancy({'ours':None},external),4)
        self.assertEqual(occupancy({'ours':30},external+[{'ppid':30}]),4)
        self.assertEqual(occupancy({'a':30,'b':None},[{'ppid':30}]),2)

    def test_coverage_requires_all_modes_and_pvt(self):
        results=[dict(corner=c,temperature_c=t,modes={str(m):dict(passed=True) for m in self.spec['modes_mhz']})
                 for c in self.spec['corners'] for t in self.spec['temperatures_c']]
        self.assertTrue(covered(results,self.spec))
        self.assertFalse(covered(results[:-1],self.spec))
        self.assertFalse(covered(results[:-1]+[results[0]],self.spec))
        bad=copy.deepcopy(results);bad[0]['modes'].pop('100')
        self.assertFalse(covered(bad,self.spec))
        bad=copy.deepcopy(results);bad[0]['modes']['400']['passed']=False
        self.assertFalse(covered(bad,self.spec))

    def test_seed_cannot_qualify_unmeasured_range(self):
        self.assertTrue(9<=seed_from_bracket(400,dict(endpoints_mhz=[372.879,426.945]))<=246)
        for endpoints in ([410,430],[420,380]):
            with self.assertRaises(ValueError):seed_from_bracket(400,dict(endpoints_mhz=endpoints))

    def test_search_requires_actual_bracket_and_native_pass(self):
        self.assertFalse(find_bracket(400,lambda c:None)['passed'])
        self.assertFalse(find_bracket(400,lambda c:[410,390])['passed'])
        gap=find_bracket(400,lambda c:[1000/(c+1),1010/(c+1)])
        self.assertFalse(gap['passed'])
        self.assertFalse(gap['global_unreachability_proven'])
        result=find_bracket(400,lambda c:[380,430])
        self.assertTrue(result['passed'])


if __name__=='__main__':
    unittest.main()
