import unittest
from fit_prototype_native_timing_surfaces_v2 import metrics, surface, interval

class FinalTimingSurfaceTests(unittest.TestCase):
    def test_pointwise_envelope_preserves_both_models(self):
        points=[(x,y,x+y+delta) for x in (.012,.12,1.) for y in (0,.1,.4) for delta in (-.001,.002)]
        lo,hi=interval(surface(points),.12,.1)
        self.assertAlmostEqual(lo,.219)
        self.assertAlmostEqual(hi,.222)

    def test_assertion_slew_belongs_only_to_control(self):
        for reset in (0,1):
            f=dict(kind='async_assert',reset_value=reset,control_pin='CONTROL')
            record=dict(output_rise_20_80_ns=[.1],output_fall_80_20_ns=[.2])
            arcs=list(metrics(f,record,'sequential'))
            asserted='rise' if reset else 'fall'
            self.assertEqual([a[0] for a in arcs if a[2]==asserted],['CONTROL'])
            self.assertEqual([a[0] for a in arcs if a[2]!=asserted],['CLK'])

    def test_clock_toggle_slew_has_both_clock_directions(self):
        f=dict(kind='clock_toggle',reset_value=0,control_pin='RESET_B')
        arcs=list(metrics(f,dict(output_rise_20_80_ns=[.1],output_fall_80_20_ns=[.2]),'sequential'))
        self.assertEqual({(a[0],a[2]) for a in arcs},{('CLK','rise'),('CLK','fall')})

if __name__=='__main__':unittest.main()
