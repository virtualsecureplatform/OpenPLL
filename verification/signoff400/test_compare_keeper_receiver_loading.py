import unittest
from compare_keeper_receiver_loading import compatible


class ReceiverComparison(unittest.TestCase):
    def fixture(self):
        d = {key: True for key in ['normal_native_replay_complete', 'all_saved_replay_values_finite', 'all_completed_native_outputs_copy_verified', 'all_physical_tuning_controls_correct', 'symbolic_boundary_reduction_used', 'literal_aggregated_samples_preserved', 'roundoff_audited_at_source_samples']}
        d.update(PLLOUT_forced=False, native_executable_sha256='pinned', max_step_ps=50, shared_knot_carrier_used=True, source_representation='shared')
        return d, dict(d)

    def test_backend_or_timestep_change_rejected(self):
        for key, value in [('native_executable_sha256', 'other'), ('max_step_ps', 10)]:
            a, b = self.fixture()
            b[key] = value
            with self.assertRaises(ValueError):
                compatible(a, b)

    def test_partial_or_forced_output_rejected(self):
        for key, value in [('normal_native_replay_complete', False), ('PLLOUT_forced', True), ('all_physical_tuning_controls_correct', False)]:
            a, b = self.fixture()
            b[key] = value
            with self.assertRaises(ValueError):
                compatible(a, b)

    def test_same_checked_settings_accepted(self):
        compatible(*self.fixture())


if __name__ == '__main__':
    unittest.main()
