from fractions import Fraction as F
import unittest
from audit_hierarchical_capacitance import flatten,number
from prepare_prototype_analog_reference import subcircuits


class HierarchicalCapacitanceControls(unittest.TestCase):
    def test_signed_parallel_terms_and_zero_R_aliases_are_exact(self):
        text='.subckt child a b\nC1 a z 2f\nC2 z b -1f\nR0 z b 0\n.ends\n.subckt top p q\nX1 p q child\nC1 p q -0.5f\n.ends\n'
        pairs,counts=flatten(subcircuits(text),'top')
        self.assertEqual(pairs,{('p','q'):F(3,2*10**15)})
        self.assertEqual(counts['expanded_capacitors'],3)
        self.assertEqual(number('-0'),0)

    def test_distinct_instances_do_not_alias_internal_nodes(self):
        text='.subckt child a b\nC1 a z 1f\nC2 z b -0.5f\n.ends\n.subckt top p q\nX1 p q child\nX2 p q child\n.ends\n'
        pairs,_=flatten(subcircuits(text),'top')
        self.assertEqual(len(pairs),4)
        self.assertEqual(sum(v<0 for v in pairs.values()),2)

    def test_unknown_numeric_and_hierarchical_models_rejected(self):
        with self.assertRaises(ValueError):number('nan')
        with self.assertRaises(ValueError):flatten(subcircuits('.subckt top a b\nX1 a b unknown\n.ends\n'),'top')


if __name__=='__main__':unittest.main()
