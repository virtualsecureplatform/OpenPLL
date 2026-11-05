import math
import unittest

from prototype_diode_charge_reference import charge_capacitance


class ChargeControls(unittest.TestCase):
    def test_each_junction_is_continuous_at_its_own_transition(self):
        for potential, grading, cap in ((.729, .44, 1.3459e-15), (.2, .0009, 3.6001e-17)):
            transition = .5 * potential
            below, cb = charge_capacitance(transition - 1e-10, cap, potential, grading)
            above, ca = charge_capacitance(transition + 1e-10, cap, potential, grading)
            self.assertLess(abs(above - below) / cap, 1e-8)
            self.assertLess(abs(ca - cb) / cap, 1e-8)

    def test_charge_derivative_matches_capacitance_on_both_sides(self):
        for potential, grading in ((.729, .44), (.2, .0009)):
            for voltage in (-1.8, -.1, 0, .0999, .1001, .4, .9):
                cap = 1e-15
                _, c = charge_capacitance(voltage, cap, potential, grading)
                a, _ = charge_capacitance(voltage - 1e-6, cap, potential, grading)
                b, _ = charge_capacitance(voltage + 1e-6, cap, potential, grading)
                self.assertTrue(math.isclose((b - a) / 2e-6, c, rel_tol=1e-7))

    def test_original_shared_offset_is_detectably_discontinuous(self):
        bottom, _ = charge_capacitance(.729 * .5, 1, .729, .44)
        sidewall, _ = charge_capacitance(.2 * .5, 1, .2, .0009)
        self.assertGreater(abs(bottom - sidewall), .3)


if __name__ == '__main__':
    unittest.main()
