import unittest
from assess_selected_einvp_enable_edges import crossings,neighborhoods


class EdgeTests(unittest.TestCase):
    def inputs(self):return [dict(time_s=float(i),direction='rise'if i%2 else'fall')for i in range(5)]

    def test_negative_threshold_delay_is_not_rejected(self):
        outputs=[dict(time_s=.9,direction='fall'),dict(time_s=2.1,direction='rise'),dict(time_s=2.9,direction='fall')]
        records=neighborhoods(self.inputs(),outputs,.5,3.5)
        self.assertEqual(len(records),3);self.assertTrue(all(r['exactly_one_inverted_output_edge']for r in records));self.assertLess(records[0]['delay_ps'],0.)

    def test_glitch_and_wrong_direction_detected(self):
        outputs=[dict(time_s=.9,direction='fall'),dict(time_s=1.1,direction='rise'),dict(time_s=2.1,direction='fall'),dict(time_s=2.9,direction='fall')]
        records=neighborhoods(self.inputs(),outputs,.5,3.5)
        self.assertEqual([r['exactly_one_inverted_output_edge']for r in records],[False,False,True])

    def test_threshold_plateau_not_double_counted(self):
        events=crossings([[0.,0.],[1.,1.8],[2.,.9],[3.,.9],[4.,0.]],1)
        self.assertEqual([e['direction']for e in events],['rise','fall']);self.assertAlmostEqual(events[0]['time_s'],.5)


if __name__=='__main__':unittest.main()
