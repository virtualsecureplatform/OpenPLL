import unittest
from verify_charge_merge_maps import compare_map

class FieldMapComparison(unittest.TestCase):
    def test_complete_map_and_invalid_native_ids(self):
        self.assertEqual(compare_map([0,2,1],[0,2,1],3),3)
        for a,b in (([0,2],[0,1]),([0,1],[0,1,2]),([1,0],[1,0]),([0,3],[0,3]),([0,-1],[0,-1]),([0,True],[0,1])):
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):compare_map(a,b,3)
