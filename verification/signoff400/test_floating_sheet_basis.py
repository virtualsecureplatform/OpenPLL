from fractions import Fraction as F
import unittest
from floating_sheet_basis import mesh,certify,energy
class FloatingSheetBasis(unittest.TestCase):
    def test_rectangles_polygons_and_holes_preserve_exact_sheet_energy(self):
        shapes=[([(0,0),(7,0),(7,3),(0,3)],[]), ([(0,0),(5,0),(5,2),(2,2),(2,4),(0,4)],[]), ([(0,0),(8,0),(8,7),(0,7)],[[(2,2),(4,2),(4,5),(2,5)]])]
        for hull,holes in shapes:
            for refinement in (1,2,4):
                with self.subTest(hull=hull,refinement=refinement):
                    result=certify(mesh(hull,holes,refinement));self.assertTrue(result['finite_R_discretization_control_passed']);self.assertFalse(result['finite_R_basis_qualified'])
    def test_nonlinear_voltage_refinement_matches_exact_error(self):
        errors=[]
        for refinement in (1,2,4,8):
            t=mesh([(0,0),(3,0),(3,2),(0,2)],refinement=refinement);values=[x*x for x,y in t['points']];exact=F(4,3)*3**3*2;error=exact-energy(t['stiffness'],values)
            self.assertEqual(error,F(3*2,3)*F(3,refinement)**2);errors.append(error)
        self.assertTrue(all(a==4*b for a,b in zip(errors,errors[1:])))
    def test_nonmanhattan_intersections_and_touching_holes_rejected(self):
        cases=[([(0,0),(3,1),(3,3),(0,3)],[]), ([(0,0),(4,0),(4,4),(0,4)],[[(0,1),(2,1),(2,2),(0,2)]])]
        for hull,holes in cases:
            with self.assertRaises(ValueError):mesh(hull,holes)
    def test_perturbed_conductance_and_mass_rejected(self):
        for key in ('stiffness','mass'):
            t=mesh([(0,0),(3,0),(3,2),(0,2)]);t[key][0,0]+=F(1,100)
            with self.assertRaises(ValueError):certify(t)
