import unittest
from review_prototype_clock_pulse_campaign import settled_assessment,thresholds
from run_prototype_clock_pulse_grid import WIDTHS


class LoadedPulseReview(unittest.TestCase):
    def test_preload_settling_observer_does_not_conceal_missing_capture(self):
        rows=[(0,0,0),(3e-9,0,1.8),(4.5e-9,1.45,1.8),(4.8e-9,1.62,1.8),
              (5e-9,1.69,1.8),(5.3e-9,1.75,1.8),(6e-9,1.8,0),(6.4e-9,1.8,1.8),
              (7e-9,0,1.8),(12e-9,0,1.8),(13e-9,0,1.8),(14e-9,0,1.8)]
        result=settled_assessment(rows,'low',0,1)
        self.assertFalse(result['original_pre_state_verified'])
        self.assertTrue(result['full_output_trace_capture_verified'])
        failed=[(r[0],1.8 if r[0]>=5e-9 else r[1],r[2]) for r in rows]
        self.assertFalse(settled_assessment(failed,'low',0,1)['full_output_trace_capture_verified'])

    def test_real_narrow_pulse_failure_retained_without_imposing_250ps_gate(self):
        rows=[dict(kind=k,nominal_width_ps=w,full_output_trace_capture_verified=not(k=='low' and w==250)) for k in ('high','low') for w in WIDTHS]
        result=thresholds(rows)
        self.assertEqual(result['low']['failing_tested_widths_ps'],[250])
        self.assertEqual(result['low']['smallest_tested_width_with_all_larger_samples_passing_ps'],400)
        self.assertFalse(result['low']['continuous_minimum_pulse_width_qualified'])
        with self.assertRaises(ValueError):thresholds(rows[:-1])


if __name__=='__main__':unittest.main()
