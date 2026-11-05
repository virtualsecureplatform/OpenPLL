import copy
import unittest
from refine_prototype_BBPD_phase import decision


def record():
    return dict(outputs={'DN':dict(detector_rising_edges_ns=[12.8,52.8],detector_falling_edges_ns=[32.8,72.8],one_toggle_per_detector_rise_observed=True,quiet_before_first_sample=True),
        'UP':dict(detector_rising_edges_ns=[],detector_falling_edges_ns=[],one_toggle_per_detector_rise_observed=True,quiet_before_first_sample=True)})


class PhaseRefinementDecisionIntegrity(unittest.TestCase):
    def test_only_two_clean_correctly_captured_pulses_produce_polarity(self):
        r=record();self.assertEqual(decision(r),'DN')
        for key,value in (('one_toggle_per_detector_rise_observed',False),('quiet_before_first_sample',False),('detector_falling_edges_ns',[32.8])):
            bad=copy.deepcopy(r);bad['outputs']['DN'][key]=value
            self.assertIsNone(decision(bad))

    def test_ambiguous_or_absent_polarity_is_not_forced_to_binary(self):
        r=record();r['outputs']['UP']['detector_rising_edges_ns']=[12.8]
        self.assertIsNone(decision(r))
        r=record();r['outputs']['DN']['detector_rising_edges_ns']=[]
        self.assertIsNone(decision(r))


if __name__=='__main__':unittest.main()
