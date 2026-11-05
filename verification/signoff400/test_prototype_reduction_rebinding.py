import unittest
from fractions import Fraction as F
from rebind_prototype_floating_reduction import bijection, capacitor_pairs


class ReductionRebinding(unittest.TestCase):
    def test_capacitor_operator_retains_signed_and_parallel_pairs(self):
        source = 'Cflat0 a b 2e-15\nCflat1 b a -1e-15\nCkron0 b c 3e-15\n'
        target = 'Cflat0 y z 3e-15\nCflat1 x y 1e-15\n'
        mapping = bijection({'o1':'a','o2':'b','o3':'c'}, {'o1':'x','o2':'y','o3':'z'})
        self.assertEqual(capacitor_pairs(source,mapping),capacitor_pairs(target))
        self.assertEqual(capacitor_pairs(source)[('a','b')],F('1e-15'))

    def test_nonfunction_merging_or_moved_rail_rejected(self):
        cases = [({'a':'x','b':'x'},{'a':'y','b':'z'}),
                 ({'a':'x','b':'y'},{'a':'z','b':'z'}),
                 ({'a':'VPWR'},{'a':'x'})]
        for source,target in cases:
            with self.subTest(source=source),self.assertRaises(ValueError):bijection(source,target)

    def test_unknown_endpoint_cannot_be_silently_omitted(self):
        with self.assertRaises(KeyError):capacitor_pairs('Cflat0 a b 1e-15',{'a':'x'})


if __name__=='__main__':unittest.main()
