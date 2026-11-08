import unittest
from queue_keeper_fast_RTL_gain_screen import candidate,gain_order
from common_v3 import spec


class GainScreen(unittest.TestCase):
    def test_predeclared_first_and_unique_complete_grid(self):
        order=gain_order(spec())
        self.assertEqual(order[0],(4,0));self.assertEqual(len(order),25)
        self.assertEqual(len(set(order)),25)

    def test_lower_unresolved_or_untested_blocks_candidate(self):
        order=[(4,0),(1,0),(1,1)]
        passing=dict(ki=1,kp=1,state='all_TT_diagnostic_cases_pass')
        self.assertIsNone(candidate([passing],order))
        lower=dict(ki=1,kp=0,state='unresolved_model_support')
        self.assertIsNone(candidate([lower,passing],order))
        lower['state']='diagnostic_failure'
        self.assertEqual(candidate([lower,passing],order),[1,1])


if __name__=='__main__':unittest.main()
