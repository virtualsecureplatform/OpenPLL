"""Controls for local cell capacitance and separated signed compensation."""
from fractions import Fraction as F
import unittest
from build_prototype_full_C_wire_R_v6 import build
from test_prototype_full_C_wire_R import SOURCE,fixture

class LocalCapacitance(unittest.TestCase):
    def test_receiver_capacitance_follows_receiver_gate(self):
        for attachment in ['driver','farthest']:
            model,metrics,_=build(SOURCE,'Top',fixture(),{'D0':'D0','R0':'R0'},attachment)
            lines=[x.split()for x in model.splitlines()]
            receiver=next(x for x in lines if x[0]=='Xflat1')
            gate=receiver[2]
            incident=[x for x in lines if x[0].startswith('Cflat')and gate in x[1:3]]
            self.assertTrue(incident)
            self.assertTrue(metrics['child_cell_capacitance_at_rewired_terminals'])
            self.assertTrue(metrics['zero_wire_R_exact_device_topology_and_C_operator_match'])
            self.assertFalse(metrics['wire_capacitance_from_SPEF_added'])

    def test_locality_does_not_hide_indefinite_compensation(self):
        model,_,_=build(SOURCE,'Top',fixture(),{'D0':'D0','R0':'R0'},'driver')
        caps=[x.split()for x in model.splitlines()if x.startswith('Cflat')]
        negative=[x for x in caps if F(x[3])<0]
        self.assertEqual(len(negative),1)
        # Set the negative pair's driver endpoint to one and every other node
        # to zero. The relocated signed correction now exposes negative energy.
        driver=negative[0][1]
        energy=sum(F(x[3])*(int(x[1]==driver)-int(x[2]==driver))**2 for x in caps)
        self.assertLess(energy,0)

if __name__=='__main__':unittest.main()
