import unittest
from summarize_prototype_DCO_points import summarize


class NativeBracketSummary(unittest.TestCase):
    def test_bracket_cannot_mix_corners_or_coarse_codes(self):
        rows=[dict(corner='ss',coarse_code=1,fine_code=8,observed_frequency_interval_hz=[300e6,301e6]),
              dict(corner='ss',coarse_code=2,fine_code=247,observed_frequency_interval_hz=[450e6,451e6])]
        self.assertTrue(all(not r['observed_target_bracket'] for r in summarize(rows)))
        rows[1]['coarse_code']=1
        result=summarize(rows)[0]
        self.assertTrue(result['observed_target_bracket'])
        self.assertFalse(result['calibration_qualified'])

    def test_duplicate_points_and_invalid_intervals_rejected(self):
        row=dict(corner='sf',coarse_code=1,fine_code=8,observed_frequency_interval_hz=[300e6,301e6])
        with self.assertRaises(ValueError):summarize([row,row])
        row['observed_frequency_interval_hz']=[301e6,300e6]
        with self.assertRaises(ValueError):summarize([row])


if __name__=='__main__':unittest.main()
