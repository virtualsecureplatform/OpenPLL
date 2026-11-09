import unittest
from reset_contract_v4 import spec,validate_assertion

class ResetContract(unittest.TestCase):
    def test_scope_and_limits_preserved(self):
        r=spec();self.assertEqual(r['model_based_scenarios'],60)
        self.assertEqual(r['frequency_error_ppm'],1000);self.assertFalse(r['release_ready'])
    def test_inclusive_minimum_and_later_assertions(self):
        for a,b in [(0,80),(100,180),(100,200)]:
            r=validate_assertion(a,b,reference_running=True,programming_static=True)
            self.assertFalse(r['physical_reset_timing_qualified'])
    def test_short_invalid_and_unsupported_conditions_rejected(self):
        for a,b,clock,static in [(0,79.999,True,True),(-1,80,True,True),(0,float('nan'),True,True),
                                 (0,80,False,True),(0,80,True,False),(True,81,True,True)]:
            with self.subTest(case=(a,b,clock,static)),self.assertRaises(ValueError):
                validate_assertion(a,b,reference_running=clock,programming_static=static)

if __name__=='__main__':unittest.main()
