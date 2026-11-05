import unittest
from inventory_prototype_interface_loading_v2 import inventory

SOURCE='''
.subckt analog OUT VGND
Xinner OUT OUT VGND VGND sky130_fd_pr__nfet_01v8 w=1 l=1
.ends analog
.subckt receiver A Y VGND
Xgate Y A VGND VGND sky130_fd_pr__nfet_01v8 w=1 l=1
Cpin A VGND 1f
.ends receiver
.subckt top VGND
Xanalog analog_out VGND analog
Ralias analog_out receiver_in 0
Xreceiver receiver_in out VGND receiver
Cparent receiver_in VGND 2f
.ends top
'''


class InterfaceAliasControls(unittest.TestCase):
    def test_internal_alias_binds_caps_and_receiver_but_excludes_analog(self):
        r=inventory(SOURCE,'top','analog','OUT')
        self.assertEqual(r['assembled_signal'],'top/receiver_in')
        self.assertEqual(len(r['incident_signed_capacitances']),1)
        self.assertEqual(r['incident_signed_capacitances'][0]['farads'],'3/1000000000000000')
        self.assertEqual(r['external_primitive_instances'],1)
        self.assertEqual(r['external_primitive_terminals'][0]['incident_terminals'],['gate'])
        self.assertFalse(r['parent_loading_complete'])

    def test_top_level_port_is_not_prefixed(self):
        text=SOURCE.replace('.subckt top VGND','.subckt top VGND receiver_in')
        r=inventory(text,'top','analog','OUT')
        self.assertEqual(r['assembled_signal'],'receiver_in')
        self.assertEqual(r['external_primitive_instances'],1)


if __name__=='__main__':unittest.main()
