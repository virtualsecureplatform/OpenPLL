import unittest
from build_prototype_full_C_wire_R_v8 import build
TEXT='''.subckt Cell A B Z VGND
Rshort A B 0
Xmos Z B VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=0.42
Cpin B VGND 1f
.ends Cell
.subckt Top IN OUT VGND
Xcell IN IN OUT VGND Cell
Ca IN VGND 2f
.ends Top
'''
def spef():return dict(nets=[dict(name='a',connections=[dict(kind='P',node='IN',direction='I'),dict(kind='I',node='cell:A',direction='I')],resistors=[dict(nodes=['IN','cell:A'],ohms='10')]),dict(name='b',connections=[dict(kind='I',node='cell:B',direction='O')],resistors=[dict(nodes=['cell:B','middle'],ohms='20')])])
class CoalescedChildWire(unittest.TestCase):
    def test_coalesced_name_retains_physical_child_join(self):
        for attachment in ['driver','farthest']:
            _,m,_=build(TEXT,'Top',spef(),{'cell':'cell'},attachment)
            self.assertTrue(m['zero_wire_R_exact_device_topology_and_C_operator_match'])
            self.assertTrue(m['coalesced_root_wire_networks'][0]['child_zero_R_join_verified'])
            self.assertFalse(m['spatial_capacitance_placement_qualified'])
    def test_same_root_name_is_insufficient_without_child_short(self):
        with self.assertRaisesRegex(ValueError,'lacks actual child zero-R'):
            build(TEXT.replace('Rshort A B 0\n',''),'Top',spef(),{'cell':'cell'})
if __name__=='__main__':unittest.main()
