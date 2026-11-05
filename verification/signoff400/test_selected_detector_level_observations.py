import unittest
from selected_detector_level_observations import decisions
class LevelObservationTest(unittest.TestCase):
    def edges(self,rises,falls,up=(),dn=()):
        return {'reference_pin':{'rising_ns':[60]},'feedback_pin':{'rising_ns':rises,'falling_ns':falls},'detector_up':{'rising_ns':up},'detector_dn':{'rising_ns':dn}}
    def test_falling_aperture_uses_level_at_lookback(self):
        e=self.edges([39.6],[59.89],dn=[62.65])
        self.assertEqual(decisions(e,90,112,False)[0]['predicted'],'dn')
        e=self.edges([39.6],[59.88],up=[62.66])
        self.assertEqual(decisions(e,90,112,False)[0]['predicted'],'up')
    def test_none_and_both_remain_explicit(self):
        for up,dn,expected in [((),(),'none'),([62.6],[62.7],'both')]:
            self.assertEqual(decisions(self.edges([39],[59],up,dn),90,112,False)[0]['decision'],expected)
    def test_initial_high_and_missing_coverage(self):
        self.assertEqual(decisions(self.edges([],[]),90,112,True)[0]['predicted'],'dn')
        with self.assertRaises(ValueError):decisions(self.edges([],[]),90,61000,False)
if __name__=='__main__':unittest.main()
