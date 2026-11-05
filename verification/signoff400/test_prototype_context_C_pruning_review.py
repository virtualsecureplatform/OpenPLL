from fractions import Fraction as F
import unittest
from review_prototype_context_C_pruning import reconcile


class ReparsedPruning(unittest.TestCase):
    def test_declared_edit_only(self):
        original = ['.subckt A x y', 'Xflat0 x y model', 'Cflat0 x 0 1e-15',
                    'Ckron0 x y 1e-20', '.ends A']
        target = original[:3] + ['CkronSparseGuard0 x 0 2e-20', 'CkronSparseGuard1 y 0 2e-20', original[-1]]
        guards = reconcile(original, target, {'Ckron0'})
        self.assertLessEqual(guards['x'][0], F('2e-20'))
        self.assertGreaterEqual(guards['x'][1], F('2e-20'))
        for before, after in [('1e-15', '2e-15'), ('Xflat0 x y model', 'Xflat0 y y model'),
                              ('CkronSparseGuard0 x 0', 'CkronSparseGuard0 x y')]:
            changed = [line.replace(before, after) for line in target]
            with self.assertRaises(ValueError):
                reconcile(original, changed, {'Ckron0'})


if __name__ == '__main__':
    unittest.main()
