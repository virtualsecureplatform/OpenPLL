import unittest
from inventory_prototype_analog_boundary import inventory

SOURCE='''
.subckt Analog IN OUT PRIVATE VPWR VGND
Xcore OUT IN VGND VGND sky130_fd_pr__nfet_01v8 l=.15 w=.4
Cown OUT PRIVATE 1f
.ends Analog
.subckt Load A Z VPWR VGND
Xload Z A VGND VGND sky130_fd_pr__nfet_01v8 l=.15 w=.4
.ends Load
.subckt Top IN OUT VPWR VGND
XA IN OUT private VPWR VGND Analog
XL OUT z VPWR VGND Load
Cpositive OUT VGND 2f
Cnegative OUT private -.1f
Cprivate private other .3f
Cunrelated VPWR VGND 100f
.ends Top
'''

class AnalogBoundaryInventory(unittest.TestCase):
    def test_all_physical_and_internal_pins_are_retained(self):
        result=inventory(SOURCE,'Top','Analog',{'IN','OUT','VPWR','VGND'})
        self.assertEqual(result['physical_macro_boundary_pins'],2)
        self.assertEqual(result['exported_internal_boundary_pins'],1)
        self.assertEqual(result['incident_geometric_pairs'],3)
        self.assertEqual(result['incident_exterior_primitive_instances'],1)
        self.assertTrue(any(row['farads'].startswith('-') for row in result['signed_incident_capacitors']))
        self.assertTrue(any('Top/other' in row['nodes'] for row in result['signed_incident_capacitors']))

    def test_target_intrinsics_and_unrelated_supply_network_are_excluded(self):
        result=inventory(SOURCE,'Top','Analog',{'IN','OUT'})
        self.assertEqual(result['exterior_counts']['primitive_instances'],1)
        self.assertEqual(len(result['boundaries']),3)
        self.assertFalse(any(row['farads']=='1/10000000000000' for row in result['signed_incident_capacitors']))


if __name__=='__main__':unittest.main()
