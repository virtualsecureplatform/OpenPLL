import unittest
from plan_keeper_static_target_point import select


class TargetSelection(unittest.TestCase):
    def test_interpolates_inside_bracket_without_using_target_measurement(self):
        p=select(8,390e6,148,410e6)
        self.assertEqual(p['selected_fine'],78)
        self.assertEqual(p['predicted_frequency_Hz'],400e6)
        self.assertGreater(p['continuous_period_code'],p['continuous_frequency_code'])

    def test_rejects_extrapolation_and_invalid_knots(self):
        for values in [(8,410e6,149,420e6),(8,380e6,149,390e6),
                       (8,float('nan'),149,410e6),(8,390e6,8,410e6),
                       (7,390e6,149,410e6),(8,410e6,149,390e6)]:
            with self.subTest(values=values),self.assertRaises(ValueError):select(*values)


if __name__=='__main__':unittest.main()
