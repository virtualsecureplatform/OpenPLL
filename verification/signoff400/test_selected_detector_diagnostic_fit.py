import unittest
from fit_selected_detector_diagnostic import fit,same_model


class SelectedDetectorFitTest(unittest.TestCase):
    def observation(self,phase,decision):
        return dict(cycles=[dict(phase_ps=phase,decision=decision)],latencies={r:{e:[2.6] for e in ['rise','fall']} for r in ['UP','DN']})

    def test_fit_uses_only_supplied_points_and_tightest_opposite_signs(self):
        values=[self.observation(-250,'dn'),self.observation(-120,'dn'),self.observation(-104,'up'),self.observation(250,'up')]
        p=fit(values)
        self.assertEqual(p['observed_transition_bracket_ps'],[-120,-104])
        self.assertEqual(p['lookback_ps'],112)
        self.assertNotIn('validated_for_prototype',p)

    def test_contradictory_sampled_signs_cannot_be_fitted(self):
        with self.assertRaisesRegex(ValueError,'bracket'):
            fit([self.observation(-100,'dn'),self.observation(-120,'up')])

    def test_mixed_physical_models_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'same physical'):
            same_model([{'native_model_sha256':{'model':'one'}},{'native_model_sha256':{'model':'two'}}])

    def test_missing_fall_timing_cannot_be_fabricated(self):
        values=[self.observation(-120,'dn'),self.observation(-104,'up')]
        for value in values:value['latencies']['DN']['fall']=[]
        with self.assertRaisesRegex(ValueError,'rise and fall'):fit(values)


if __name__=='__main__':unittest.main()
