import unittest
from build_prototype_full_C_wire_R_v4 import build
from test_prototype_full_C_wire_R import SOURCE,fixture


class FloatingCapacitanceLift(unittest.TestCase):
    def test_floating_annotations_preserve_the_single_voltage_map(self):
        annotated=SOURCE.replace('0.4f','0.4f $ **FLOATING').replace('-0.2f','-0.2f $ **FLOATING')
        for mode in ('driver','farthest'):
            plain,_,base=build(SOURCE,'Top',fixture(),{'D0':'D0','R0':'R0'},mode)
            mapped,metrics,lift=build(annotated,'Top',fixture(),{'D0':'D0','R0':'R0'},mode)
            self.assertEqual(mapped,plain);self.assertEqual(lift,base)
            self.assertTrue(metrics['one_hot_capacitance_voltage_map'])
            self.assertTrue(metrics['zero_wire_R_exact_device_topology_and_C_operator_match'])


if __name__=='__main__':unittest.main()
