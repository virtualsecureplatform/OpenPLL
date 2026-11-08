import unittest
from collect_keeper_TT_characterization import characterize

class TTCharacterization(unittest.TestCase):
    def points(self):return [dict(fine=i,frequency_hz=370e6+200000*i) for i in [8,110,149,182,247]]
    def holdout(self):return dict(fine=133,frequency_hz=396.6e6)
    def test_bracket_and_independent_interpolation(self):
        r=characterize(self.points(),self.holdout());self.assertEqual(r['target']['lower']['fine'],149);self.assertEqual(r['target']['upper']['fine'],182);self.assertEqual(r['independent_holdout']['predictions'][0]['error_ppm'],0);self.assertFalse(r['interpolation_accuracy_accepted'])
    def test_holdout_leakage_rejected(self):
        with self.assertRaises(ValueError):characterize([*self.points(),self.holdout()],self.holdout())
    def test_holdout_extrapolation_rejected(self):
        with self.assertRaises(ValueError):characterize(self.points(),dict(fine=1,frequency_hz=370.2e6))
    def test_nonmonotonic_fit_rejected(self):
        p=self.points();p[2]['frequency_hz']=380e6
        with self.assertRaises(ValueError):characterize(p,self.holdout())
    def test_nonfinite_frequency_rejected(self):
        with self.assertRaises(ValueError):characterize(self.points(),dict(fine=133,frequency_hz=float('nan')))
    def test_target_outside_range_reported(self):
        self.assertFalse(characterize(self.points(),self.holdout(),500e6)['target']['measured_bracket_available'])

if __name__=='__main__':unittest.main()
