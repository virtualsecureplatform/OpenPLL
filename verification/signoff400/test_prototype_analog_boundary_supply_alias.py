import unittest
from inventory_prototype_analog_boundary_v2 import inventory

SOURCE='''
.subckt Analog IN OUT SUB
Xcore OUT IN SUB SUB sky130_fd_pr__nfet_01v8 l=.15 w=.4
.ends Analog
.subckt Load A Z G
Xdevice Z A G G sky130_fd_pr__nfet_01v8 l=.15 w=.4
.ends Load
.subckt Top IN OUT VPWR VGND
XA IN OUT VGND Analog
Xload OUT z VGND Load
Xunrelated b a VGND Load
Cload OUT VGND 2f
Cunrelated z VGND 100f
.ends Top
'''

class GroundAliasBoundary(unittest.TestCase):
    def test_exported_substrate_ground_is_not_a_signal_boundary(self):
        r=inventory(SOURCE,'Top','Analog',{'IN','OUT'})
        self.assertEqual({n['pin'] for n in r['boundaries']},{'IN','OUT'})
        self.assertEqual(r['incident_exterior_primitive_instances'],1)
        self.assertEqual(r['incident_geometric_pairs'],1)
        self.assertIn('VGND',r['signed_incident_capacitors'][0]['nodes'])

    def test_true_internal_signal_remains_an_exterior_boundary(self):
        text=SOURCE.replace('XA IN OUT VGND Analog','XA IN OUT internal Analog')
        r=inventory(text,'Top','Analog',{'IN','OUT'})
        self.assertEqual({n['pin'] for n in r['boundaries']},{'IN','OUT','SUB'})
        self.assertEqual(r['exported_internal_boundary_pins'],1)


if __name__=='__main__':unittest.main()
