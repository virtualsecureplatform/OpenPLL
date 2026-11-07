import unittest
from search_selected_TT_gains_v2 import selection_audit


class GainSelectionOrder(unittest.TestCase):
    def row(self,ki,kp,state):return dict(ki=ki,kp=kp,disposition=state)
    def test_missing_lower_coverage_stays_unresolved(self):
        r=selection_audit([self.row(1,0,'missing_native_coverage'),self.row(1,1,'pass')],(1,1))
        self.assertFalse(r['selection_order_resolved']);self.assertEqual(r['unresolved_lower_gain_pairs'],[[1,0]])
    def test_unassessed_lower_pair_stays_unresolved(self):
        self.assertFalse(selection_audit([self.row(1,1,'pass')],(1,1))['selection_order_resolved'])
    def test_actual_lower_functional_failure_resolves_order(self):
        self.assertTrue(selection_audit([self.row(1,0,'functional_failure'),self.row(1,1,'pass')],(1,1))['selection_order_resolved'])
    def test_higher_unknown_pair_does_not_invalidate_lowest_candidate(self):
        self.assertTrue(selection_audit([self.row(1,0,'pass'),self.row(4,0,'missing_native_coverage')],(1,0))['selection_order_resolved'])
    def test_false_candidate_or_skipped_lower_pass_rejected(self):
        with self.assertRaises(ValueError):selection_audit([self.row(1,0,'functional_failure')],(1,0))
        with self.assertRaises(ValueError):selection_audit([self.row(1,0,'pass'),self.row(1,1,'pass')],(1,1))


if __name__=='__main__':unittest.main()
