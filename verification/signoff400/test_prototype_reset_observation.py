import unittest
from prototype_reset_observation import compare


class ResetObservation(unittest.TestCase):
    def test_named_scalar_and_bus_bits_and_missing_values(self):
        expected = {'READY': 0, 'CODE[7]': 1}
        values = {'v(ready)': 0.01, 'v(code[7])': 1.79}
        self.assertTrue(compare(expected, values, 1.8)['all_defined_reset_bits_match'])
        result = compare(expected, {'v(ready)': 0.01}, 1.8)
        self.assertFalse(result['all_defined_reset_bits_match'])
        self.assertEqual(result['missing_root_observations'], ['CODE[7]'])

    def test_wrong_and_midrail_values_are_not_accepted(self):
        for voltage in (1.8, 0.9):
            result = compare({'READY': 0}, {'v(ready)': voltage}, 1.8)
            self.assertFalse(result['all_defined_reset_bits_match'])
            self.assertEqual(result['mismatched_or_indeterminate_bits'], ['READY'])

    def test_rejects_vacuous_unknown_nonfinite_and_aliased_expectations(self):
        for expected, values, supply in (({}, {}, 1.8), ({'A': 2}, {}, 1.8),
            ({'A': 0}, {'v(a)': float('nan')}, 1.8),
            ({'A': 0, 'a': 0}, {}, 1.8), ({'A': 0}, {}, 0)):
            with self.assertRaises(ValueError):
                compare(expected, values, supply)


if __name__ == '__main__':
    unittest.main()
