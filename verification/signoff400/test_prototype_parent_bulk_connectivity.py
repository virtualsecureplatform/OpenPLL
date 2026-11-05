import unittest
from check_prototype_parent_bulk_connectivity_v2 import trace


class BulkConnectivityTests(unittest.TestCase):
    def test_hierarchical_rail_alias_and_body_binding(self):
        text = '''.subckt cell A B
X0 A A A well sky130_fd_pr__nfet_01v8 w=1 l=0.15
R0 well B 0
.ends
.subckt top VPWR VGND VPB VNB
Xn VPWR VNB cell
Xp VGND VGND VGND VPB sky130_fd_pr__pfet_01v8 w=1 l=0.15
.ends
'''
        self.assertTrue(trace(text, 'top')['all_MOS_bulk_terminals_connected_to_correct_parent_rail'])
        bad = text.replace('Xn VPWR VNB cell', 'Xn VPWR floating cell')
        result = trace(bad, 'top')
        self.assertEqual(len(result['unexpected_bulk_connections']), 1)

    def test_signal_or_opposite_supply_bulk_rejected(self):
        for node in ('VPWR', 'internal'):
            text = f'''.subckt top VPWR VGND VPB VNB
X0 VPWR VPWR VGND {node} sky130_fd_pr__nfet_01v8 w=1 l=0.15
.ends
'''
            self.assertFalse(trace(text, 'top')['all_MOS_bulk_terminals_connected_to_correct_parent_rail'])

    def test_rail_short_and_positive_resistance_not_idealized(self):
        text = '''.subckt top VPWR VGND VPB VNB
X0 VGND VGND VGND floating sky130_fd_pr__nfet_01v8 w=1 l=0.15
R0 floating VNB 1e-18
.ends
'''
        self.assertFalse(trace(text, 'top')['all_MOS_bulk_terminals_connected_to_correct_parent_rail'])
        with self.assertRaises(ValueError):
            trace(text.replace('R0 floating VNB 1e-18', 'R0 VPWR VGND 0'), 'top')

    def test_local_well_names_do_not_merge_between_instances(self):
        text = '''.subckt cell B
X0 B B B well sky130_fd_pr__nfet_01v8 w=1 l=0.15
R0 well B 0
.ends
.subckt top VPWR VGND VPB VNB
Xa VNB cell
Xb VPWR cell
.ends
'''
        result = trace(text, 'top')
        self.assertEqual(result['expanded_MOS_instances'], 2)
        self.assertEqual(len(result['unexpected_bulk_connections']), 1)
        self.assertEqual(result['unexpected_bulk_connections'][0]['instance'], 'top/Xb/X0')

    def test_two_terminal_poly_resistor_does_not_supply_a_bulk(self):
        text = '''.subckt top VPWR VGND VPB VNB
X0 VGND VGND VGND floating sky130_fd_pr__nfet_01v8 w=1 l=0.15
X1 floating VNB sky130_fd_pr__res_generic_po w=0.48 l=0.5
.ends
'''
        result = trace(text, 'top')
        self.assertFalse(result['all_MOS_bulk_terminals_connected_to_correct_parent_rail'])
        self.assertEqual(result['primitive_models']['sky130_fd_pr__res_generic_po'], 1)
        with self.assertRaises(ValueError):
            trace(text.replace('res_generic_po', 'unknown_unreviewed_model'), 'top')
