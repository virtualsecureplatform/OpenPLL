import unittest
from review_prototype_final_clock_pulses import observe, thresholds


class FinalPulseReviewTests(unittest.TestCase):
    def trace(self,premature=False):
        def ramp(t,a,b,lo,hi):return lo if t<=a else hi if t>=b else lo+(hi-lo)*(t-a)/(b-a)
        result=[]
        for i in range(181):
            t=i/10
            start,end=(9.6,9.8) if premature else (10.6,11.2)
            q=ramp(t,3,6,0,1.8) if t<start else ramp(t,start,end,1.8,0)
            clk=ramp(t,2.8,3.2,0,1.8) if t<9.8 else ramp(t,9.8,10.2,1.8,0) if t<=10.2 else ramp(t,10.2,10.6,0,1.8)
            result.append((t*1e-9,q,clk))
        return result

    def test_valid_settled_capture_and_premature_output_edge(self):
        self.assertTrue(observe(self.trace(),'low',400,0,1,400)['full_output_trace_capture_verified'])
        self.assertFalse(observe(self.trace(True),'low',400,0,1,400)['full_output_trace_capture_verified'])

    def test_declared_pulse_width_and_slew_must_match_waveform(self):
        with self.assertRaisesRegex(ValueError,'clock edges'):
            observe(self.trace(),'low',600,0,1,400)
        with self.assertRaisesRegex(ValueError,'clock slew'):
            observe(self.trace(),'low',400,0,1,20)

    def test_failing_short_pulses_and_nonmonotonic_samples_preserved(self):
        cases=[dict(kind=k,nominal_width_ps=w,full_output_trace_capture_verified=w!=400)
               for k in ('high','low') for w in (400,600,1000,1600)]
        self.assertEqual(thresholds(cases)['low']['smallest_tested_width_with_all_larger_samples_passing_ps'],600)
        next(c for c in cases if c['kind']=='low' and c['nominal_width_ps']==1000)['full_output_trace_capture_verified']=False
        self.assertEqual(thresholds(cases)['low']['smallest_tested_width_with_all_larger_samples_passing_ps'],1600)
        self.assertEqual(thresholds(cases)['low']['failing_tested_widths_ps'],[400,1000])


if __name__=='__main__':unittest.main()
