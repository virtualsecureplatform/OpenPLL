import unittest
from fractions import Fraction as F
from check_prototype_junction_conversion_v3 import inventory,match


class JunctionConversionControls(unittest.TestCase):
    def test_half_unit_decimal_rounding_and_source_drain_exchange(self):
        raw=[tuple(map(F,('0.092625','0.935','0.08775','0.92')))]
        native=[tuple(map(F,('0.09262','0.935','0.08775','0.92')))]
        self.assertIsNotNone(match(raw,native))
        self.assertIsNotNone(match(raw,[native[0][2:]+native[0][:2]]))
        self.assertIsNone(match(raw,[tuple(map(F,('0.09260','0.935','0.08775','0.92')))]))
        self.assertIsNone(match(raw+raw,native))

    def test_zero_terminal_attribute_uses_extracted_node_diffusion_geometry(self):
        node='node VGND 0 0 0 0 m1 '+' '.join(map(str,[0]*8+[9240,556]+[0]*4))+'\n'
        ext=node+'device msubckt sky130_fd_pr__nfet_01v8_lvt 95 85 96 86 l=200 w=84 VNB VPWR 400 0 VGND 0 0 VGND 168 4452,274\n'
        spice='.subckt cell\nX0 VGND VPWR VGND VNB sky130_fd_pr__nfet_01v8_lvt l=1 w=0.42 as=0.231 ps=2.78 ad=0.1113 pd=1.37\n.ends\n'
        a,b=inventory(ext,spice,F(1,200));key=next(iter(a))
        self.assertIsNotNone(match(a[key],b[key]))
        with self.assertRaises(ValueError):inventory(ext.removeprefix(node),spice,F(1,200))


if __name__=='__main__':unittest.main()
