import unittest
from search_selected_TT_gains import grid,disposition

class GainSearch(unittest.TestCase):
    def test_first_trial_and_lowest_gain_order_are_distinct(self):
        first,pairs=grid({'gain_search':dict(first=[4,0],ki=[4,1,2],kp=[2,0,1])})
        self.assertEqual(first,(4,0));self.assertEqual(pairs,[(i,p)for i in(1,2,4)for p in(0,1,2)])
    def case(self,**change):
        row=dict(state='diagnostic_simulation_completed',native_exit=0,terminal_marker_present=True,functional_trace_pass=True,reference_phase_coverage_pass=True);row.update(change);return row
    def test_missing_coverage_and_execution_failure_cannot_reject_gain(self):
        self.assertEqual(disposition([self.case(state='needs_native_tuning_points',native_exit=1)]),'missing_native_coverage')
        self.assertEqual(disposition([self.case(native_exit=1)]),'incomplete_execution')
        self.assertEqual(disposition([self.case(terminal_marker_present=False)]),'incomplete_execution')
    def test_only_completed_functional_failure_allows_expansion(self):
        self.assertEqual(disposition([self.case()]),'pass')
        self.assertEqual(disposition([self.case(state='diagnostic_failed',functional_trace_pass=False)]),'functional_failure')
        self.assertEqual(disposition([self.case(reference_phase_coverage_pass=False)]),'functional_failure')
        with self.assertRaises(ValueError):disposition([])

if __name__=='__main__':unittest.main()
