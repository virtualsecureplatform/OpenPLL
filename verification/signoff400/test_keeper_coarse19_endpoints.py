import unittest
from queue_keeper_coarse19_endpoints import checked_point, BACKEND


class EndpointGuards(unittest.TestCase):
    def point(self):
        native = dict(normal_native_completion=True, all_saved_native_values_finite=True, stationary_requested_code=True, native_executable_sha256=BACKEND, BSIM_PBSWGD_default_corrected=True, requested_coarse=19, requested_fine=149, max_step_ps=50, frequency_diagnostic=dict(frequency_mhz=401.0))
        controls = dict(all_macro_and_DCO_tuning_bits_match=True, mismatched_endpoints=0, observed_bits=302, observed_endpoint_voltages=604, coarse=19, fine=149)
        return native, controls

    def test_completed_correct_point_accepted(self):
        self.assertEqual(checked_point(*self.point(), 149), 401.0)

    def test_old_backend_or_other_band_or_step_rejected(self):
        for key, value in [('native_executable_sha256', 'old'), ('requested_coarse', 20), ('max_step_ps', 10)]:
            native, controls = self.point()
            native[key] = value
            with self.assertRaises(ValueError):
                checked_point(native, controls, 149)

    def test_physical_mismatch_rejected(self):
        native, controls = self.point()
        controls['mismatched_endpoints'] = 1
        with self.assertRaises(ValueError):
            checked_point(native, controls, 149)

    def test_missing_frequency_is_explicit(self):
        native, controls = self.point()
        native['frequency_diagnostic'] = None
        self.assertIsNone(checked_point(native, controls, 149))


if __name__ == '__main__':
    unittest.main()
