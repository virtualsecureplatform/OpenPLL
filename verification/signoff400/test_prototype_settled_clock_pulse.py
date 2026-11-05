import unittest
from run_prototype_final_clock_pulse_point import assess as early
from run_prototype_final_clock_pulse_point_v2 import assess as settled


class SettledPulseTests(unittest.TestCase):
    def rows(self,end):
        def ramp(t,a,b,low,high):
            return low if t<=a else high if t>=b else low+(high-low)*(t-a)/(b-a)
        rows=[]
        for i in range(181):
            t=i/10
            q=ramp(t,3,end,0,1.8) if t<10.6 else ramp(t,10.6,11.2,1.8,0)
            clock=ramp(t,2.8,3.2,0,1.8) if t<9.8 else ramp(t,9.8,10.2,1.8,0) if t<=10.2 else ramp(t,10.2,10.6,0,1.8)
            rows.append((t*1e-9,q,clock))
        return rows

    def test_long_preload_fixes_fixture_without_relaxing_voltage_threshold(self):
        rows=self.rows(6)
        self.assertFalse(early(rows,'low',0,1)['pre_state_verified'])
        result=settled(rows,'low',0,1)
        self.assertTrue(result['pre_state_verified'])
        self.assertTrue(result['full_output_trace_capture_verified'])
        self.assertAlmostEqual(result['observed_clock_pulse_width_ps'],400)

    def test_still_unsettled_preload_is_rejected(self):
        self.assertFalse(settled(self.rows(10.5),'low',0,1)['pre_state_verified'])
        self.assertFalse(settled(self.rows(10.5),'low',0,1)['full_output_trace_capture_verified'])


if __name__=='__main__':unittest.main()
