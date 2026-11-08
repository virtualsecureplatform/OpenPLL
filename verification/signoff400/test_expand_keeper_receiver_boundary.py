import unittest
from expand_keeper_receiver_boundary import expand


class ReceiverExpansion(unittest.TestCase):
    text = '''.subckt top PLLOUT CTRL VPWR VGND
X1 receiver PLLOUT VGND VGND sky130_fd_pr__nfet_01v8
X2 receiver PLLOUT VPWR VPWR sky130_fd_pr__pfet_01v8
X3 downstream receiver VGND VGND sky130_fd_pr__nfet_01v8
X4 downstream receiver VPWR VPWR sky130_fd_pr__pfet_01v8
X5 downstream CTRL VGND VGND sky130_fd_pr__nfet_01v8
C1 receiver aggressor 1f
C2 downstream VGND 2f
.ends top
'''

    def test_receiver_freed_and_downstream_frontier_reported(self):
        model, interface, added = expand(self.text, {'X1', 'X2'}, 'receiver')
        self.assertEqual(added, ['X3', 'X4'])
        self.assertIn('receiver', interface['interior_nodes'])
        self.assertIn('downstream', interface['externally_driven_ports'])
        self.assertIn('aggressor', interface['externally_driven_ports'])
        self.assertIn('C1 receiver aggressor 1f', model)
        self.assertNotIn('X5 downstream', model)

    def test_formal_receiver_cannot_be_silently_freed(self):
        with self.assertRaises(ValueError):
            expand(self.text.replace('top PLLOUT CTRL', 'top receiver PLLOUT CTRL'), {'X1', 'X2'}, 'receiver')

    def test_no_expansion_rejected(self):
        with self.assertRaises(ValueError):
            expand(self.text, {'X1', 'X2', 'X3', 'X4'}, 'receiver')


if __name__ == '__main__':
    unittest.main()
