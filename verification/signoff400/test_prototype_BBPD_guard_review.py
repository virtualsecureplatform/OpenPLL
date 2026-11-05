import unittest
from review_prototype_BBPD_corrected_waveforms import measure


def fixture(phase):
    def pulse(t,centers):
        for c in centers:
            if c-.1<=t<=c+.1:return 1.8*(t-c+.1)/.2
            if c+.1<t<c+19.9:return 1.8
            if c+19.9<=t<=c+20.1:return 1.8*(c+20.1-t)/.2
        return 0
    ref=[10.1,50.1,90.1];div=[c+phase/1000 for c in ref]
    times=sorted({0.,1.,1.1,1.2,5.,8.,85.,90.,*(c+d for c in ref+div for d in (-.1,0,.1,19.9,20,20.1) if 0<=c+d<=90)})
    return [(t*1e-9,pulse(t,ref),pulse(t,div),0 if t<=1 else 1.8 if t>=1.2 else (t-1)*9,0,0,0,0) for t in times]


class NativeInputGuardIntegrity(unittest.TestCase):
    def test_negative_phase_guard_is_retained_outside_two_cycle_analysis(self):
        for phase in (-1000,0,1000):
            result=measure(fixture(phase),phase)
            self.assertTrue(result['full_input_guard_edges_verified'])
            self.assertEqual(len(result['measured_analysis_phase_ps']),2)
            for v in result['measured_analysis_phase_ps']:self.assertAlmostEqual(v,phase)
            self.assertFalse(result['native_interface_qualified'])

    def test_missing_actual_guard_edge_is_not_silently_ignored(self):
        rows=fixture(-1000)
        bad=[(*r[:2],0,*r[3:]) if r[0]>=88e-9 else r for r in rows]
        with self.assertRaisesRegex(ValueError,'clock/phase/guard'):measure(bad,-1000)


if __name__=='__main__':unittest.main()
