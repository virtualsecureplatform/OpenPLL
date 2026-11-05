import unittest
from review_prototype_BBPD_loaded_bias import bracket,decision


def observation(phase,role):
    outputs={name:dict(detector_rising_edges_ns=[12.8,52.8] if name==role else [],detector_falling_edges_ns=[32.8,72.8] if name==role else [],one_toggle_per_detector_rise_observed=True,quiet_before_first_sample=False) for name in ('DN','UP')}
    sync={name:dict(quiet_output_low_rail_screen_pass=True,one_delayed_capture_per_source_toggle_observed=True) for name in ('DN','UP')}
    return dict(phase_ps=phase,outputs=outputs,first_synchronizers=sync)


class LoadedDetectorBias(unittest.TestCase):
    def test_unknown_does_not_shrink_known_transition_interval(self):
        result=bracket([observation(-100,'DN'),observation(-50,None),observation(-25,'UP')])
        self.assertEqual(result['observed_transition_bracket_ps'],[-100,-25])
        self.assertEqual(result['unresolved_phase_points_ps'],[-50])
        self.assertFalse(result['qualified_uncertainty_bound'])

    def test_actual_capture_failure_invalidates_decision(self):
        row=observation(-100,'DN')
        self.assertEqual(decision(row['outputs'],row['first_synchronizers']),'DN')
        row['first_synchronizers']['DN']['quiet_output_low_rail_screen_pass']=False
        self.assertIsNone(decision(row['outputs'],row['first_synchronizers']))

    def test_reversed_or_duplicate_points_not_used_as_single_bias(self):
        self.assertIsNone(bracket([observation(-100,'UP'),observation(-25,'DN')])['observed_transition_bracket_ps'])
        with self.assertRaises(ValueError):bracket([observation(-100,'DN'),observation(-100,'UP')])


if __name__=='__main__':unittest.main()
