import unittest
from selected_dco_history_sources import hold_after
class HistoryHoldTest(unittest.TestCase):
    def test_hold_interpolates_at_cut_and_preserves_prefix(self):
        self.assertEqual(hold_after([(0,0),(1,1),(3,3)],2,3),[(0,0),(1,1),(2,2),(3,2)])
    def test_hold_exact_knot_does_not_duplicate_time(self):
        self.assertEqual(hold_after([(0,0),(1,1),(3,3)],1,3),[(0,0),(1,1),(3,1)])
    def test_insufficient_coverage_rejected(self):
        with self.assertRaises(ValueError):hold_after([(0,0),(1,1)],.5,3)
if __name__=='__main__':unittest.main()
