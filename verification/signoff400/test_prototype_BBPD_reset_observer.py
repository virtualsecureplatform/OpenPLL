import unittest
from observe_prototype_BBPD_reset import measure


def fixture(reset=15,glitch=False):
    def pulse(t,centers):
        for c in centers:
            if c-.1<=t<=c+.1:return (t-c+.1)*9
            if c+.1<t<c+19.9:return 1.8
            if c+19.9<=t<=c+20.1:return (c+20.1-t)*9
        return 0
    ref=[10.1,50.1,90.1];div=[9.1,49.1,89.1]
    times=sorted({0.,5.,8.,20.,21.,49.6,75.,85.,90.,reset,reset+.1,reset+.2,52.7,52.8,52.9,53.1,53.2,53.3,72.7,72.8,72.9,
        *(c+d for c in ref+div for d in (-.1,0,.1,19.9,20,20.1) if 0<=c+d<=90)})
    result=[]
    for t in times:
        rst=0 if t<=reset else 1.8 if t>=reset+.2 else (t-reset)*9
        dn=.4 if glitch and 20<=t<=21 else pulse(t,[52.8])
        q=0 if t<=53.1 else 1.8 if t>=53.3 else (t-53.1)*9
        result.append((t*1e-9,pulse(t,ref),pulse(t,div),rst,dn,0,q,0))
    return result


class ResetReleaseObserverIntegrity(unittest.TestCase):
    def test_late_reset_requires_quiet_until_next_reference_and_one_capture(self):
        for release in (15,25,35):
            r=measure(fixture(release),-1000,release)
            self.assertTrue(r['reset_capture_control_pass'])
            self.assertEqual(r['first_allowed_reference_ns'],50.1)
            self.assertEqual(r['outputs']['DN']['expected_events'],1)
            self.assertEqual(r['outputs']['UP']['expected_events'],0)
            self.assertFalse(r['native_interface_qualified'])

    def test_pre_sample_glitch_below_half_supply_is_not_hidden_by_edge_counts(self):
        r=measure(fixture(glitch=True),-1000,15)
        self.assertTrue(r['outputs']['DN']['controlled_pulses_pass'])
        self.assertFalse(r['outputs']['DN']['quiet_before_first_post_reset_sample'])
        self.assertFalse(r['reset_capture_control_pass'])
        with self.assertRaises(ValueError):measure(fixture(15),-1000,25)


if __name__=='__main__':unittest.main()
