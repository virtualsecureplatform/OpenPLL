import unittest
from fractions import Fraction as F
from prune_prototype_context_C import select, replay


class PositiveEdgePruning(unittest.TestCase):
    def test_exact_guard_and_unchanged_budget(self):
        edges = [('c0', 'a', 'b', F(3)), ('c1', 'b', 'c', F(2))]
        chosen, loads = select(edges, {'a': F(6), 'b': F(10), 'c': F(4)})
        self.assertEqual(chosen, {'c0', 'c1'})
        self.assertEqual(loads, {'a': F(6), 'b': F(10), 'c': F(4)})
        proof = replay(edges, sorted(chosen), loads, loads,
                       {n: F(100) for n in 'abc'}, F(1, 10), F(1, 5))
        self.assertEqual(proof['maximum_normalized_final_row_error'], '1/5')
        # The correction is [[3,3,0],[3,5,2],[0,2,2]]. Its row
        # sums equal the emitted guards and it is weakly diagonally dominant.
        correction = [[F(3), F(3), F(0)], [F(3), F(5), F(2)], [F(0), F(2), F(2)]]
        for i, row in enumerate(correction):
            self.assertEqual(sum(abs(x) for x in row), loads['abc'[i]])
            self.assertGreaterEqual(row[i], sum(abs(x) for j, x in enumerate(row) if j != i))

    def test_insufficient_guard_and_forged_budget_fail(self):
        edges = [('c', 'a', 'b', F(3))]
        scales = {'a': F(100), 'b': F(100)}
        with self.assertRaises(ValueError):
            replay(edges, ['c'], {'a': F(5), 'b': F(6)}, {'a': F(5), 'b': F(6)}, scales, F(0), F(1))
        with self.assertRaises(ValueError):
            replay(edges, ['c'], {'a': F(6), 'b': F(6)}, {'a': F(6), 'b': F(6)}, scales, F(0), F(1, 100))
        with self.assertRaises(ValueError):
            replay(edges, ['unknown'], {}, {}, scales, F(0), F(1))

    def test_shared_node_capacity_prevents_overallocation(self):
        edges = [('x', 'a', 'b', F(3)), ('y', 'b', 'c', F(3))]
        chosen, loads = select(edges, {n: F(6) for n in 'abc'})
        self.assertEqual(len(chosen), 1)
        self.assertEqual(loads['b'], F(6))
        chosen, loads = select(edges, {n: F(1) for n in 'abc'})
        self.assertEqual(chosen, set())
        self.assertEqual(loads, {})


if __name__ == '__main__':
    unittest.main()
