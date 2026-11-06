import unittest
from selected_receiver_uncertainty import apply

class CaptureStressTest(unittest.TestCase):
    def test_late_choice_preserves_width_and_leaves_distant_event(self):
        edges=[(.98,1),(1.2,0),(2.75,1),(2.9,0)]
        out,records=apply(edges,[1,2,3,4],'late_window',100)
        self.assertAlmostEqual(out[0][0],1.001);self.assertAlmostEqual(out[1][0]-out[0][0],.22)
        self.assertEqual(out[2:],edges[2:]);self.assertGreater(records[0]['extra_delivery_delay_ns'],0)
        nominal,_=apply(edges,[1,2,3,4],'nominal',100);self.assertEqual(nominal,edges)

    def test_invalid_or_reordered_inputs_rejected(self):
        for clocks,edges in [([2,1],[(.98,1)]),([1,2],[(.98,1),(.99,1)]),([1,2],[(.95,1),(.96,0),(.97,1)])]:
            with self.assertRaises(ValueError):apply(edges,clocks,'late_window',100)
        with self.assertRaises(ValueError):apply([(.98,1)],[1,2],'late_window',float('nan'))

if __name__=='__main__':unittest.main()
