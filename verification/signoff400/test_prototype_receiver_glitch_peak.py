import unittest
from run_prototype_receiver_glitch_peak import targeted_phases


class GlitchPeakTargeting(unittest.TestCase):
    def test_measured_peak_included_and_prior_grid_not_repeated(self):
        rows=[(7.82e-9,0,0,0,0,0,.2),(7.845e-9,0,0,0,0,0,.45),(7.86e-9,0,0,0,0,0,.1)]
        phases,peak=targeted_phases(rows)
        self.assertIn(2845,phases)
        self.assertIn(2835,phases)
        self.assertIn(2855,phases)
        self.assertTrue(all(p%250 for p in phases))
        self.assertAlmostEqual(peak['voltage_v'],.45)

    def test_missing_window_or_peak_outside_targetable_interior_rejected(self):
        for rows in ([],[(5e-9,0,0,0,0,0,.45)]):
            with self.assertRaises(ValueError):targeted_phases(rows)


if __name__=='__main__':unittest.main()
