import unittest
from compare_prototype_DCO_scope_controls import command_identity,differences

class ScopeComparisonTests(unittest.TestCase):
    def test_scope_path_changes_do_not_hide_solver_changes(self):
        a=['worker','--rcx-netlist','a','--build-dir','x','--ngspice-reltol','1e-5']
        b=['worker','--rcx-netlist','b','--build-dir','y','--ngspice-reltol','1e-5']
        self.assertEqual(command_identity(a),command_identity(b))
        b[-1]='1e-6'
        self.assertNotEqual(command_identity(a),command_identity(b))

    def test_signed_scope_shift_and_R_effect_kept_separate(self):
        r=differences(395e6,400e6,410e6)
        self.assertEqual(r['conventional_wire_R_effect_hz'],-5e6)
        self.assertEqual(r['zero_R_capacitance_scope_shift_hz'],10e6)
        self.assertEqual(r['additive_scope_corrected_finite_R_estimate_hz'],405e6)
        self.assertTrue(r['additive_estimate_is_not_a_measured_full_C_finite_R_result'])
        with self.assertRaises(ValueError):differences(1,float('nan'),2)

if __name__=='__main__':unittest.main()
