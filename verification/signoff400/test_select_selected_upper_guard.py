import unittest
from select_selected_upper_guard import choose

class UpperGuardTest(unittest.TestCase):
    def point(self,f,mhz):return dict(coarse=20,fine=f,frequency_hz=mhz*1e6)
    def test_request_is_a_code_not_a_frequency(self):
        r=choose([self.point(111,392.31),self.point(112,392.67),self.point(133,400.1)])
        self.assertEqual((r['state'],r['fine']),('measurement_needed',165));self.assertNotIn('frequency_hz',r);self.assertFalse(r['predicted_frequency_assigned'])
    def test_covered_and_bank_boundary(self):
        self.assertEqual(choose([self.point(133,400),self.point(165,412)])['state'],'upper_code_coverage_already_measured')
        self.assertEqual(choose([self.point(247,400)])['state'],'bank_limit_requires_review')
        self.assertEqual(choose([self.point(240,400)])['fine'],247)
    def test_invalid_measurements_rejected(self):
        for rows in [[],[self.point(111,392),self.point(111,393)],[self.point(7,392)],[self.point(111,float('nan'))]]:
            with self.assertRaises(ValueError):choose(rows)

if __name__=='__main__':unittest.main()
