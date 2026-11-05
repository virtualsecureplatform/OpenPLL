import unittest
from compare_prototype_analog_devices_v2 import devices
from prepare_prototype_analog_reference import subcircuits


class DeviceComparisonControls(unittest.TestCase):
    def netlist(self,width='1',node='z'):
        return subcircuits('.subckt sky130_fd_sc_hd__test a b\nX0 a '+node+' b b sky130_fd_pr__nfet_01v8 w='+width+' l=0.15\n.ends\n.subckt top p q\nXsky130_fd_sc_hd__test_0 p q sky130_fd_sc_hd__test\n.ends\n')

    def test_numeric_format_is_normalized_but_geometry_and_connectivity_changes_are_retained(self):
        a=devices(self.netlist(),'top')
        self.assertEqual(a,devices(self.netlist('1.0'),'top'))
        self.assertNotEqual(a,devices(self.netlist('2'),'top'))
        self.assertNotEqual(a,devices(self.netlist(node='other'),'top'))

    def test_unknown_primitive_is_not_silently_ignored(self):
        b=self.netlist();b['sky130_fd_sc_hd__test']=b['sky130_fd_sc_hd__test'].replace('sky130_fd_pr__nfet_01v8','unreviewed_model')
        with self.assertRaises(ValueError):devices(b,'top')


if __name__=='__main__':unittest.main()
