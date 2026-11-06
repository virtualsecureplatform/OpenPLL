import copy
import unittest
from compare_selected_history_code_pair import increments


class HistoryCodePairTest(unittest.TestCase):
    def comparison(self, candidate, native):
        return dict(frequency_comparisons={name:dict(window_after_first_rise_ns=window,
            candidate=dict(frequency_mhz=candidate),full_native=dict(frequency_mhz=native),
            difference_ppm=1e6*(candidate/native-1)) for name,window in
            [('common',[10,40]),('early',[10,25]),('late',[25,40])]})

    def test_increment_is_measured_without_refitting(self):
        first=self.comparison(392.2,392.2)
        good=increments(first,self.comparison(392.6,392.6))
        self.assertTrue(all(r['increment_error_percent']==0 for r in good))
        poor=increments(first,self.comparison(392.5,392.6))
        self.assertAlmostEqual(poor[0]['increment_error_percent'],-25)

    def test_short_mismatched_nonfinite_or_nonpositive_increments_rejected(self):
        first=self.comparison(392.2,392.2); second=self.comparison(392.6,392.6)
        damaged=copy.deepcopy(second);damaged['frequency_comparisons']['late']['window_after_first_rise_ns']=[25,39]
        for bad in (damaged,self.comparison(392.2,392.6),self.comparison(392.6,392.1),self.comparison(float('nan'),392.6)):
            with self.subTest(bad=bad),self.assertRaises(ValueError):increments(first,bad)


if __name__=='__main__':unittest.main()
