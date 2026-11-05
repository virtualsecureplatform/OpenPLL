from fractions import Fraction as F
import unittest
from build_prototype_full_C_wire_R_v3 import build
from test_prototype_full_C_wire_R import SOURCE,fixture
from check_prototype_capacitance_paths import certify


def pairs(model):
    return {tuple(sorted(f[1:3])):F(f[3]) for line in model.splitlines() for f in [line.split()] if f and f[0].startswith('Cflat')}


class LocalCapacitanceWireTests(unittest.TestCase):
    def test_cell_C_stays_at_receiver_and_needs_a_new_passivity_proof(self):
        driver,metrics,_=build(SOURCE,'Top',fixture(),{'D0':'D0','R0':'R0'},'driver')
        far,_,_=build(SOURCE,'Top',fixture(),{'D0':'D0','R0':'R0'},'farthest')
        devices=[line.split() for line in driver.splitlines() if line.startswith('Xflat')]
        receiver_gate=devices[1][2];driver_output=devices[0][1]
        self.assertTrue(any(receiver_gate in pair and value==F('.4e-15') for pair,value in pairs(driver).items()))
        self.assertNotEqual(receiver_gate,driver_output)
        self.assertFalse(certify(pairs(driver))['passivity_certified'])
        self.assertTrue(certify(pairs(far))['passivity_certified'])
        self.assertTrue(metrics['cell_local_C_at_actual_routed_terminals'])
        self.assertTrue(metrics['zero_wire_R_exact_device_topology_and_C_operator_match'])
        self.assertFalse(metrics['one_hot_capacitance_voltage_map'])

    def test_without_macro_C_attachment_variant_cannot_move_cell_C(self):
        text=SOURCE.replace('Cshield wire rpriv -0.2f\n','')
        a,_,_=build(text,'Top',fixture(),{'D0':'D0','R0':'R0'},'driver')
        b,_,_=build(text,'Top',fixture(),{'D0':'D0','R0':'R0'},'farthest')
        self.assertEqual(a,b)

if __name__=='__main__':unittest.main()
