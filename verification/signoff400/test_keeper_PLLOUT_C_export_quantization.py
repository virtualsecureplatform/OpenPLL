import unittest
from fractions import Fraction as F
from audit_keeper_PLLOUT_C_export_quantization import reconcile
class Quantization(unittest.TestCase):
    def test_zeroed_mass_and_positive_rounding_reconcile(self):
        n={'small':F(1,2*10**18),'positive':F(1000001,10**21),'zero':F(0)};p={'small':F(0),'positive':F(1,10**15),'zero':F(0)};r=reconcile(n,p)
        self.assertEqual(r['positive_native_couplings_printed_zero'],1);self.assertTrue(r['exact_total_discrepancy_reconciled']);self.assertFalse(r['dynamic_frequency_or_timing_error_qualified'])
    def test_tiny_negative_native_residual_is_accounted(self):
        r=reconcile({'residual':-F(1,10**36)},{'residual':F(0)})
        self.assertEqual(r['native_negative_pairs_printed_zero'],1);self.assertTrue(r['exact_total_discrepancy_reconciled'])
    def test_endpoint_mismatch_and_large_zeroed_cap_rejected(self):
        with self.assertRaisesRegex(ValueError,'inventory'):reconcile({'a':F(1)},{'b':F(1)})
        with self.assertRaisesRegex(ValueError,'sub-attofarad'):reconcile({'a':F(1,10**18)},{'a':F(0)})
if __name__=='__main__':unittest.main()
