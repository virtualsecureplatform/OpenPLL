from copy import deepcopy
import unittest
from compare_prototype_native_sequential_models import fixtures, paired, pwl


class SequentialComparisonTests(unittest.TestCase):
    def test_holdout_covers_all_five_masters_and_both_kinds(self):
        rows = [dict(corner='ss',kind='sequential',fixture=dict(master=master,
                    kind=kind,external_load_pf=load,full_ramp_ps=200))
                for master in ('dfrtp1','dfrtp2','dfrtp4','dfstp1','dfstp4')
                for kind in ('clock_toggle','async_assert') for load in (0,.02,.08)]
        before = deepcopy(rows)
        cases = fixtures(rows,'ss')
        self.assertEqual(rows,before)
        self.assertEqual(len(cases),20)
        self.assertTrue(all(f['full_ramp_ps']==400 and f['external_load_pf']==.04 for f in cases))
        for i in range(0,20,2):
            self.assertEqual([f['comparison_model'] for f in cases[i:i+2]],['retained','final_C'])

    def test_paired_differences_reject_mismatched_stimulus_and_failed_state(self):
        cases=[dict(master='ff',external_load_pf=.04,comparison_model=kind)
               for kind in ('retained','final_C')]
        records=[dict(passed=True,clock_to_q_rise_ns=[.2,.21],output_rise_20_80_ns=[.3,.31]),
                 dict(passed=True,clock_to_q_rise_ns=[.205,.207],output_rise_20_80_ns=[.31,.30])]
        row=paired(cases,records)[0]
        for a,b in zip(row['paired_difference_ps']['clock_to_q_rise_ns'],[5,-3]):
            self.assertAlmostEqual(a,b)
        bad=deepcopy(cases);bad[1]['external_load_pf']=.08
        with self.assertRaisesRegex(ValueError,'stimulus differs'): paired(bad,records)
        bad=deepcopy(records);bad[1]['passed']=False
        with self.assertRaisesRegex(ValueError,'nonpassing'): paired(cases,bad)

    def test_reject_overlapping_pwl_ramps(self):
        with self.assertRaisesRegex(ValueError,'increase'): pwl([(0,0),(1,1),(1,0)])


if __name__=='__main__': unittest.main()
