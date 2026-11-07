import unittest
from build_prototype_full_C_wire_R_v7 import build

class ChildAliasWires(unittest.TestCase):
    def test_distinct_parent_wires_join_at_child_zero_R_alias(self):
        text='''.subckt Cell A B Z VGND
Rshort A B 0
Xmos Z B VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=0.42
Cpin B VGND 1f
.ends Cell
.subckt Top IN ALIAS OUT VGND
Xcell IN ALIAS OUT VGND Cell
Ca IN VGND 2f
Cb ALIAS VGND 3f
.ends Top
'''
        nets=[]
        for name,pin in [('IN','A'),('ALIAS','B')]:
            nets.append(dict(name=name,connections=[dict(kind='P',node=name,direction='I'),dict(kind='I',node='cell:'+pin,direction='I')],resistors=[dict(nodes=[name,'cell:'+pin],ohms='10')],capacitors=[]))
        for attachment in ['driver','farthest']:
            model,metrics,_=build(text,'Top',dict(nets=nets),{'cell':'cell'},attachment)
            self.assertTrue(metrics['zero_wire_R_exact_device_topology_and_C_operator_match'])
            resistors=[x.split()for x in model.splitlines()if x.startswith('Rwire')]
            self.assertEqual(len(resistors),2)
            # Both routed branches meet only at the actual aliased cell pins.
            self.assertEqual(resistors[0][2],resistors[1][2])
            self.assertNotEqual(resistors[0][1],resistors[1][1])

if __name__=='__main__':unittest.main()
