import unittest
from build_prototype_full_C_wire_R_v9 import build
from test_prototype_full_C_wire_R import SOURCE,fixture

class ExportedCouplingInterface(unittest.TestCase):
    def test_exported_internal_conductor_stays_connected(self):
        text=SOURCE.replace('.subckt Top IN OUT VPWR VGND','.subckt Top IN OUT TAP VPWR VGND').replace('wire','TAP')
        for attachment in ['driver','farthest']:
            model,metrics,_=build(text,'Top',fixture(),{'D0':'D0','R0':'R0'},attachment)
            aliases=[row.split()for row in model.splitlines()if row.startswith('Rinterface')]
            self.assertTrue(any(row[1]=='TAP'and row[2]!='TAP'and row[3]=='0'for row in aliases))
            self.assertTrue(metrics['zero_wire_R_exact_device_topology_and_C_operator_match'])
            self.assertTrue(metrics['all_literal_top_ports_bound'])
            self.assertFalse(metrics['spatial_capacitance_placement_qualified'])

if __name__=='__main__':unittest.main()
