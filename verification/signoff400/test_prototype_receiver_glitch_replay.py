import unittest
from run_prototype_receiver_glitch_replay import assess,replay_points


class GlitchReplay(unittest.TestCase):
    def test_transient_wrong_capture_rejected_even_if_final_state_recovers(self):
        rows=[(0,0,0,0),(4e-9,0,0,0),(5e-9,1.8,.45,1.8),(6e-9,0,0,0),(11e-9,0,0,0)]
        self.assertFalse(assess(rows,False)['state_retained'])
        self.assertEqual(assess(rows,False)['unexpected_threshold_crossings'],2)

    def test_entire_state_envelope_checked_below_half_supply(self):
        rows=[(0,0,0,0),(4e-9,0,0,0),(5e-9,1.8,.45,.3),(11e-9,0,0,0)]
        self.assertFalse(assess(rows,False)['state_retained'])
        self.assertEqual(assess(rows,False)['unexpected_threshold_crossings'],0)

    def test_complete_window_required_and_complement_preserved(self):
        with self.assertRaises(ValueError):replay_points([(5e-9,0,0,0,0,0,.4)],6,False)
        rows=[(5e-9+i*1e-11,0,0,0,0,0,.4) for i in range(301)]
        points=replay_points(rows,6,True)
        self.assertAlmostEqual(points[2][1],1.4)


if __name__=='__main__':unittest.main()
