import copy
import unittest
from build_prototype_BBPD_receiver_RC import build

TEXT='''.subckt buf A X VGND VNB VPB VPWR
X0 X A VGND VNB sky130_fd_pr__nfet_01v8 w=.65 l=.15
Clocal A VGND 1f
.ends buf
.subckt prototype_BBPD_receiver n_1 n_2 VGND VNB VPB VPWR
Xreceiver_0 n_1 n_2 VGND VNB VPB VPWR buf
.ends prototype_BBPD_receiver
'''
MAP={'physical_bindings':[dict(routed_instance='r',master='buf',functional_pins={'A':'n_1','X':'n_2','VGND':'VGND','VNB':'VNB','VPB':'VPB','VPWR':'VPWR'})]}


def fixture():
    a=dict(net='input',logical_bit=1,selected_terminals=[dict(routed_instance='r',pin='A',spef_node='r:A')],
        all_named_terminal_connections=[dict(kind='P',node='IN',direction='I'),dict(kind='I',node='r:A',direction='I')],
        resistors=[dict(nodes=['IN','r:A'],ohms='10')],capacitors=[dict(nodes=['r:A'],farads='1/1000000000000000'),dict(nodes=['r:A','r:X'],farads='1/1000000000000000')])
    b=dict(net='output',logical_bit=2,selected_terminals=[dict(routed_instance='r',pin='X',spef_node='r:X')],
        all_named_terminal_connections=[dict(kind='I',node='r:X',direction='O'),dict(kind='I',node='outside:D',direction='I')],
        resistors=[dict(nodes=['r:X','outside:D'],ohms='20')],capacitors=[dict(nodes=['r:X'],farads='1/1000000000000000'),dict(nodes=['r:X','r:A'],farads='1/1000000000000000'),dict(nodes=['r:X','external:1'],farads='2/1000000000000000')])
    return {'networks':[a,b]}


class ReceiverRCModelIntegrity(unittest.TestCase):
    def test_mirrored_coupling_once_external_terminal_explicit_and_local_C_retained(self):
        text,r=build(TEXT,MAP,fixture())
        self.assertEqual(r['wire_resistors'],2)
        self.assertEqual(r['wire_capacitors'],4)
        self.assertEqual(r['rewired_selected_terminals'],2)
        self.assertEqual(r['off_network_aggressors'],[{'port':'aggressor_0','spef_node':'external:1'}])
        self.assertIn('Clocal A VGND 1f',text)
        self.assertFalse(r['off_network_terminals_implicitly_grounded'])
        self.assertTrue(r['exact_wire_element_reparse_pass'])

    def test_missing_or_inconsistent_mirror_and_zero_R_are_rejected(self):
        a=fixture();a['networks'][1]['capacitors'].pop(1)
        b=fixture();b['networks'][1]['capacitors'][1]['farads']='3/1000000000000000'
        c=fixture();c['networks'][0]['resistors'][0]['ohms']='0'
        for bad in (a,b,c):
            with self.assertRaises(ValueError):build(TEXT,MAP,bad)
        with self.assertRaises(ValueError):build(TEXT.replace('Xreceiver_0 n_1','Xreceiver_0 unexpected'),MAP,fixture())


if __name__=='__main__':unittest.main()
