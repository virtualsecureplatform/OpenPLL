import unittest
from plan_selected_feedback_driver_cut import stimulus_roles


class FeedbackDriverCutTest(unittest.TestCase):
    def test_cut_moves_to_inputs_and_never_prescribes_Q(self):
        d=dict(pins={'Q':'q','CLK':'clk','D':'data','RESET_B':'reset'})
        old={'reference':'ref','feedback':'q','event_reset':'event_reset'}
        new=stimulus_roles(old,d)
        self.assertNotIn('feedback',new);self.assertNotIn('q',new.values())
        self.assertEqual(new['feedback_ff_clock'],'clk')
        self.assertEqual(new['feedback_ff_data'],'data')
        self.assertEqual(new['feedback_ff_reset'],'reset')
        self.assertEqual(old['feedback'],'q')

    def test_rejects_wrong_output_identity_and_shared_input_cut(self):
        with self.assertRaisesRegex(ValueError,'selected driver Q'):
            stimulus_roles({'feedback':'other'},{'pins':{'Q':'q','CLK':'clk','D':'data','RESET_B':'reset'}})
        with self.assertRaisesRegex(ValueError,'independent physical'):
            stimulus_roles({'reference':'ref','feedback':'q'},{'pins':{'Q':'q','CLK':'ref','D':'data','RESET_B':'reset'}})


if __name__=='__main__':unittest.main()
