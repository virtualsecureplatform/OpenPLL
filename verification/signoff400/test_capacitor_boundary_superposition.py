import math
import unittest
from probe_capacitor_boundary_superposition import response

class ClosedFormResponse(unittest.TestCase):
    def test_constant_boundaries_leave_dc_equilibrium(self):
        for t in [0., .5, 1., 2.]:
            self.assertEqual(response([0.,1.],[.7,.7],[1.2,1.2],t,1.,1.),1.)
    def test_ramp_and_final_hold_match_independent_solution(self):
        # Unit R and C: total C=6, aggregate boundary slope=1+3*2=7.
        end=8.-7.*math.exp(-1./6.)
        self.assertAlmostEqual(response([0.,1.],[0.,1.],[0.,2.],1.,1.,1.),end)
        self.assertAlmostEqual(response([0.,1.],[0.,1.],[0.,2.],2.,1.,1.),1.+(end-1.)*math.exp(-1./6.))
    def test_reciprocal_resistance_capacitance_scaling(self):
        for t in [0.,.1e-9,.77e-9,3e-9,6e-9]:
            args=([0.,.77e-9,4e-9],[0.,1.8,-.2],[.3,.1,1.4],t)
            self.assertAlmostEqual(response(*args,1e3,1e-12),response(*args,1e6,1e-15))

if __name__=='__main__':unittest.main()
