import unittest
from fit_prototype_detector_model import predict,fit


class DetectorFit(unittest.TestCase):
    def test_native_startup_history_and_loaded_aperture_polarity(self):
        self.assertEqual(predict(20000,62.5),['UP','DN'])
        self.assertEqual(predict(30000,62.5),['UP','DN'])
        self.assertEqual(predict(-75,62.5),['DN','DN'])
        self.assertEqual(predict(-50,62.5),['UP','UP'])

    def test_contradictory_broad_phase_evidence_rejected(self):
        wide=[dict(phase_ps=20000,reference_decisions=[dict(decision='DN'),dict(decision='DN')])]
        with self.assertRaisesRegex(ValueError,'contradicts'):fit(wide,dict(observed_transition_bracket_ps=[-75,-50]))

    def test_unknown_loaded_point_retained_as_unresolved(self):
        outputs={role:dict(detector_rising_edges_ns=[t],detector_falling_edges_ns=[t+20]) for role,t in (('UP',12.8),('DN',52.8))}
        wide=[dict(phase_ps=20000,outputs=outputs,reference_decisions=[dict(decision='UP'),dict(decision='DN')])]
        unknown=dict(phase_ps=-62,outputs={r:dict(detector_rising_edges_ns=[],detector_falling_edges_ns=[]) for r in ('DN','UP')},first_synchronizers={})
        p=fit(wide,dict(observed_transition_bracket_ps=[-75,-50],observations=[unknown]))
        self.assertEqual(p['unresolved_bias_points_ps'],[-62])
        self.assertFalse(p['qualified_uncertainty_bound'])


if __name__=='__main__':unittest.main()
