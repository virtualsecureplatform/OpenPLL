import unittest
from review_keeper_reset_pulse_campaigns import validate_rows, summary


class CompletedPulseReview(unittest.TestCase):
    def fixture(self):
        case=dict(master='cell',width_ps=2000,full_ramp_ps=20,load_fF=1,reset_state=0,negative_control=False)
        row=dict(corner='tt',**case,opposite_prestate_verified=True,final_state_verified=True,
                 reset_released_verified=True,stimulus_verified=True,fixture_passed=True)
        return dict(corners=['tt'],cases=[case]),row

    def test_incomplete_duplicate_and_unplanned_rows_rejected(self):
        plan,row=self.fixture()
        validate_rows(plan,[row])
        for rows in ([],[row,row],[dict(row,width_ps=100)]):
            with self.assertRaises(ValueError):validate_rows(plan,rows)

    def test_failure_cannot_be_reclassified_as_pass(self):
        plan,row=self.fixture()
        with self.assertRaises(ValueError):validate_rows(plan,[dict(row,final_state_verified=False)])
        validate_rows(plan,[dict(row,final_state_verified=False,fixture_passed=False)])

    def test_all_75_common_pulse_cases_required(self):
        _,row=self.fixture()
        rows=[dict(row,corner=c,master='sky130_fd_sc_hs__'+m,full_ramp_ps=r)
              for c in ('tt','ff','ss','sf','fs')
              for m in ('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_2') for r in (20,400,1600)]
        self.assertTrue(summary(rows)['all_declared_2ns_pulse_observations_pass'])
        with self.assertRaises(ValueError):summary(rows[:-1])
        rows[0]=dict(rows[0],fixture_passed=False)
        self.assertFalse(summary(rows)['all_declared_2ns_pulse_observations_pass'])


if __name__ == '__main__':
    unittest.main()
