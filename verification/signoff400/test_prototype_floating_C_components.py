import unittest
from inventory_prototype_floating_C_components import components


class FloatingComponentInventory(unittest.TestCase):
    def test_wire_and_primitive_nodes_are_retained_and_floats_grouped(self):
        text='.subckt Top IN OUT VPWR VGND\nXflat0 OUT IN VGND VGND sky130_fd_pr__nfet_01v8 l=.15 w=.4\nRwire0 OUT mid 1\nCflat0 mid float1 1e-15\nCflat1 float1 float2 2e-15\nCflat2 float2 VGND 1e-15\nCflat3 isolated1 isolated2 1e-15\n.ends Top\n'
        rows,stats=components(text,'Top')
        self.assertEqual(stats['capacitor_only_nodes'],4)
        self.assertEqual(stats['floating_components'],2)
        self.assertEqual(stats['floating_components_without_retained_boundary'],1)
        self.assertEqual(next(r for r in rows if 'float1' in r['nodes'])['boundaries'],['VGND','mid'])


if __name__=='__main__':unittest.main()
