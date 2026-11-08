import unittest
import numpy as np
from run_keeper_reset_pulse_grid_v2 import assess


class ResetPulseObservations(unittest.TestCase):
    def test_real_capture_and_no_pulse_control_require_opposite_prestate(self):
        t = np.array([0, 8, 9, 10, 11, 18, 21, 22]) * 1e-9
        ctrl = np.array([0, 1.8, 1.8, 0, 1.8, 1.8, 1.8, 1.8])
        for state in (0, 1):
            q = np.array([state, 1-state, 1-state, state, state, state, state, state]) * 1.8
            self.assertTrue(assess(t, q, ctrl, state, False)['fixture_passed'])
            no_pulse = np.array([0, 1.8, 1.8, 1.8, 1.8, 1.8, 1.8, 1.8])
            q[1:] = (1-state)*1.8
            self.assertTrue(assess(t, q, no_pulse, state, True)['fixture_passed'])
            self.assertFalse(assess(t, q, ctrl, state, False)['fixture_passed'])

    def test_truncated_and_nonfinite_waveforms_rejected(self):
        for t in [np.array([0, 21e-9]), np.array([0, float('nan'), 22e-9])]:
            with self.assertRaises(ValueError):
                assess(t, np.zeros(len(t)), np.zeros(len(t)), 0, False)

    def test_pulse_must_release_and_retained_state_must_be_valid(self):
        t = np.array([0, 8, 9, 10, 18, 21, 22])*1e-9
        q = np.array([0, 1.8, 1.8, 0, .9, .9, .9])
        ctrl = np.array([0, 1.8, 1.8, 0, 1.8, 1.8, 1.8])
        self.assertFalse(assess(t, q, ctrl, 0, False)['fixture_passed'])
        q[4:] = 0
        ctrl[4:] = 0
        self.assertFalse(assess(t, q, ctrl, 0, False)['fixture_passed'])


if __name__ == '__main__':
    unittest.main()
