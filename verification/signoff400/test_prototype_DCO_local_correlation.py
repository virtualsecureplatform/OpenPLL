import unittest
from prepare_prototype_DCO_local_correlation import select_codes

class LocalNativeCorrelation(unittest.TestCase):
    def test_shifted_seed_keeps_two_points_out_of_fit(self):
        seed,fit,holdouts=select_codes({88:399.675e6,89:399.912e6,90:400.204e6,91:400.445e6,92:400.736e6})
        self.assertEqual(seed,89);self.assertEqual(fit,{88,89,90});self.assertEqual(holdouts,{91,92})
        self.assertFalse(fit&holdouts)

    def test_missing_or_edge_seed_requires_more_native_data(self):
        for values in ({1:399e6,2:400e6,4:401e6,5:402e6,6:403e6},{1:400e6,2:401e6,3:402e6,4:403e6,5:404e6}):
            with self.assertRaises(ValueError):select_codes(values)

if __name__=='__main__':unittest.main()
