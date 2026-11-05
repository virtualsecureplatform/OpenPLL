import cmath
from fractions import Fraction as F
import unittest
from native_axis_stubs import augment,schur_eliminate,port_admittance
class NativeAxisStubs(unittest.TestCase):
    def test_finite_end_states_preserve_exact_native_DC_graph(self):
        native=augment([0,0,10,2],0,[(2,'a'),(5,'b'),(8,'c')],[F(3,2),F(7,4)],1,'stub',refinement=1)
        self.assertEqual(len(native['end_stub_nodes']),2);self.assertEqual(native['edges'][1:3],native['native_edges']);self.assertEqual(native['knots'][0][0],0);self.assertEqual(native['knots'][-1][0],10)
        expected={('a','a'):F(2,3),('a','b'):F(-2,3),('b','a'):F(-2,3),('b','b'):F(2,3)+F(4,7),('b','c'):F(-4,7),('c','b'):F(-4,7),('c','c'):F(4,7)}
        for refinement in (1,2,4):
            model=augment([0,0,10,2],0,[(2,'a'),(5,'b'),(8,'c')],[F(3,2),F(7,4)],1,'stub',refinement)
            self.assertEqual(schur_eliminate(model['conductance'],model['latent_nodes']),expected)
    def test_dynamic_open_line_converges_to_independent_continuum_solution(self):
        for omega in (.1,1.,10.):
            exact=cmath.sqrt(1j*omega)*cmath.tanh(cmath.sqrt(1j*omega));errors=[]
            for refinement in (1,2,4,8):
                model=augment([0,0,1,1],0,[(0,'drive'),(F(1,2),'middle')],[F(1,2)],1,'end',refinement)
                actual,residual=port_admittance(model,'drive',omega);self.assertLessEqual(residual,1e-12);self.assertGreaterEqual(actual.real,0);errors.append(abs(actual-exact))
            self.assertTrue(all(b<a for a,b in zip(errors,errors[1:])));self.assertLess(errors[-1],errors[0]/20)
    def test_no_constant_clamp_or_floating_ground_is_added(self):
        m=augment([0,0,1,1],0,[(0,'drive'),(F(1,2),'mid')],[F(1,2)],1,'stub')
        actual,_=port_admittance(m,'drive',1.);nearest_anchor=2+1j/6-(-2+1j/12)**2/(2+1j*F(2,3));self.assertGreater(abs(actual-nearest_anchor),.01);self.assertEqual(set(m['native_nodes']),{'drive','mid'});self.assertFalse(m['physical_domain_complete']);self.assertNotIn('REF',{n for _,n in m['knots']})
    def test_zero_R_outside_and_missing_units_are_rejected(self):
        for knots,resistances,sheet in [([(0,'a'),(1,'b')],[0],1),([(-1,'a'),(1,'b')],[1],1),([(0,'a'),(1,'b')],[1],0)]:
            with self.assertRaises(ValueError):augment([0,0,1,1],0,knots,resistances,sheet,'stub')

    def test_repeated_native_identity_keeps_the_original_parallel_graph(self):
        model=augment([0,0,10,2],0,[(2,'a'),(5,'b'),(8,'a')],[F(1),F(2)],1,'stub',refinement=2)
        expected={('a','a'):F(3,2),('b','b'):F(3,2),('a','b'):F(-3,2),('b','a'):F(-3,2)}
        self.assertEqual(schur_eliminate(model['conductance'],model['latent_nodes']),expected)
