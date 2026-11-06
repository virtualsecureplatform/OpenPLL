import unittest
from selected_frequency_interpolation import build

class FrequencyInterpolationTest(unittest.TestCase):
    def test_period_and_frequency_models_are_distinct_and_keep_native_knots(self):
        native={(20,10):320_000_000_000,(20,12):480_000_000_000};before=dict(native)
        period,report=build(native,'linear_period');frequency,_=build(native,'linear_frequency')
        self.assertEqual(period[20,11],384_000_000_000)
        self.assertEqual(frequency[20,11],400_000_000_000)
        for k,v in native.items():self.assertEqual(period[k],v)
        self.assertEqual(native,before)
        self.assertEqual(report['interpolated_points'][0]['origin'],'interpolated_estimate')
        self.assertFalse(report['uniform_frequency_error_bound_qualified'])

    def test_no_extrapolation_or_cross_bank_filling(self):
        table,report=build({(20,10):100,(20,12):120,(21,20):200})
        self.assertEqual(set(table),{(20,10),(20,11),(20,12),(21,20)})
        self.assertNotIn((20,9),table);self.assertNotIn((20,13),table)
        self.assertNotIn((21,11),table);self.assertFalse(report['extrapolation_allowed'])

    def test_adjacent_native_codes_need_no_estimates_and_invalid_inputs_reject(self):
        table,r=build({(20,111):392310317573,(20,112):392670114203})
        self.assertEqual(len(table),2);self.assertEqual(r['interpolated_points'],[])
        for value in [{}, {(20,7):100}, {(20,10):0}, {(20,10):float('inf')}]:
            with self.assertRaises(ValueError):build(value)
        with self.assertRaises(ValueError):build({(20,10):100},'extrapolate')

if __name__=='__main__':unittest.main()
