import unittest
from fractions import Fraction as F
from build_prototype_full_C_wire_R_v10 import build
from test_prototype_full_C_wire_R import SOURCE,fixture

class NestedWireResistance(unittest.TestCase):
    def test_existing_internal_resistors_survive_parent_rewiring(self):
        text=SOURCE.replace('Cinternal A Z 0.4f','Cinternal A Z 0.4f\nRinternal A Z 17')
        for attachment in ['driver','farthest']:
            model,m,_=build(text,'Top',fixture(),{'D0':'D0','R0':'R0'},attachment)
            retained=[x.split()for x in model.splitlines()if x.startswith('Rexisting')]
            self.assertEqual(len(retained),2)
            self.assertTrue(all(F(x[3])==17 for x in retained))
            self.assertEqual(m['existing_positive_resistors_retained'],2)
            self.assertTrue(m['existing_resistor_topology_recovered'])
            self.assertTrue(m['zero_wire_R_exact_device_topology_and_C_operator_match'])
    def test_negative_existing_resistance_is_rejected(self):
        text=SOURCE.replace('Cinternal A Z 0.4f','Cinternal A Z 0.4f\nRinternal A Z -17')
        with self.assertRaises(ValueError):build(text,'Top',fixture(),{'D0':'D0','R0':'R0'})

if __name__=='__main__':unittest.main()
