import unittest
from compare_keeper_coupling_export import metrics


class CouplingExport(unittest.TestCase):
    base = '.subckt top a b g\nC1 a b 4f\nC2 a g 3f\n.ends\n'
    old = '.subckt top a b g\nR1 a n 1\nC1 a b 4f\nC2 n g 7f\n.ends\n'
    new = '.subckt top a b g\nR1 a n 1\nC1 a b 4f\nC2 n g 3f\n.ends\n'

    def test_duplicate_grounding_removed_without_dynamic_claim(self):
        result = metrics(self.base, self.old, self.new)
        self.assertTrue(result['literal_named_R_network_unchanged'])
        self.assertTrue(result['candidate_contraction']['exact_device_and_C_contraction_verified'])
        self.assertEqual(result['candidate_total_absolute_contracted_C_error_F_exact'], '0')
        self.assertNotEqual(result['previous_total_absolute_contracted_C_error_F_exact'], '0')
        self.assertFalse(result['coupling_placement_qualified'])
        self.assertFalse(result['native_simulation_allowed'])

    def test_changed_resistor_is_not_hidden_by_contraction(self):
        result = metrics(self.base, self.old, self.new.replace('R1 a n 1', 'R1 a n 2'))
        self.assertFalse(result['literal_named_R_network_unchanged'])
        self.assertTrue(result['candidate_contraction']['exact_aggregated_C_match'])

    def test_remaining_error_is_reported_exactly(self):
        result = metrics(self.base, self.old, self.new.replace('3f', '3.00001f'))
        self.assertFalse(result['candidate_contraction']['exact_aggregated_C_match'])
        self.assertNotEqual(result['candidate_total_absolute_contracted_C_error_F_exact'], '0')


if __name__ == '__main__':
    unittest.main()
