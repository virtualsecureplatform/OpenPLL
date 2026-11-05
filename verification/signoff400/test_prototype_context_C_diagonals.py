import unittest
from fractions import Fraction as F
from review_prototype_parent_context_C import diagonal_values


class ContextDiagonals(unittest.TestCase):
    def test_signed_couplings_are_summed_without_grounding_remote_nodes(self):
        pairs={('a','b'):F(-2),('a','g'):F(1),('b','remote'):F(3)}
        self.assertEqual(diagonal_values(pairs,{'a','b'}),{'a':F(-1),'b':F(1)})
        self.assertEqual(pairs[('b','remote')],3)

    def test_missing_conductor_is_not_reported_as_zero_capacitance(self):
        with self.assertRaises(ValueError):diagonal_values({('a','b'):F(1)},{'missing'})


if __name__=='__main__':unittest.main()
