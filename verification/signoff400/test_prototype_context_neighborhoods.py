import unittest
from fractions import Fraction as F
from compare_prototype_context_neighborhoods import comparison, matrix_rows
from project_prototype_fixed_rail_C_v2 import FIXED


class NeighborhoodRowsTests(unittest.TestCase):
    def test_signed_diagonal_cancellation_and_fixed_projection(self):
        pairs = {('a', 'b'): F(3), ('a', FIXED): F(-2), ('b', FIXED): F(4)}
        # [[1,-3],[-3,7]]: absolute row sums are 4 and 10.
        self.assertEqual(matrix_rows(pairs), {'a': F(4), 'b': F(10)})
        rows, changed = comparison(pairs, pairs)
        self.assertEqual(changed, 0)
        self.assertTrue(all(r['relative_row_difference'] == 0 for r in rows))

    def test_added_coupling_has_both_diagonal_and_offdiagonal_error(self):
        rows, changed = comparison({('a', FIXED): F(2)},
                                   {('a', FIXED): F(2), ('a', 'b'): F(1)})
        by_node = {r['node']: r for r in rows}
        self.assertEqual(changed, 1)
        self.assertEqual(by_node['a']['relative_row_difference'], 1)
        self.assertEqual(by_node['b']['matrix_row_absolute_difference_F'], '2')
        self.assertIsNone(by_node['b']['relative_row_difference'])


if __name__ == '__main__':
    unittest.main()
