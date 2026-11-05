import copy
import unittest
from extend_prototype_receiver_synchronizers import extend


def fixture():
    text='.subckt sky130_fd_sc_hs__dfrtp_1 CLK D Q RESET_B VGND VNB VPB VPWR\nCcell D VGND 1f\n.ends sky130_fd_sc_hs__dfrtp_1\n.subckt prototype_BBPD_receiver_RC n_3071 n_3074 VGND VNB VPB VPWR\nRwire0 n_3071 wire_dn 1\nRwire1 n_3074 wire_up 2\nCwire0 wire_dn VGND 2f\n.ends prototype_BBPD_receiver_RC\n'
    metadata={'interface':['n_3071','n_3074','VGND','VNB','VPB','VPWR']}
    bound={'networks':[]};module={'cells':{}};physical={'chains':[{'cells':[]}]}
    for bit,name,r,clk in ((3071,'dn','1',3397),(3074,'up','2',3391)):
        bound['networks'].append(dict(logical_bit=bit,resistors=[dict(nodes=['source_'+name,name+':D'],ohms=r)],outside_terminals=[dict(kind='I',node=name+':D',direction='I')]))
        module['cells'][name]=dict(type='sky130_fd_sc_hs__dfrtp_1',connections={'D':[bit],'CLK':[clk],'RESET_B':[1362],'Q':[bit+100]})
        physical['chains'][0]['cells'].append(dict(routed_instance=name,extracted_instance='physical_'+name,master='sky130_fd_sc_hs__dfrtp_1'))
    return text,metadata,bound,module,physical


class SynchronizerExtension(unittest.TestCase):
    def test_real_sink_wire_node_used_and_existing_RC_preserved(self):
        text,mapping=extend(*fixture())
        self.assertIn('Xfirstsync_DN SYNC_CLK_DN wire_dn SYNC_DN_Q SYNC_RESET_N',text)
        self.assertIn('Rwire0 n_3071 wire_dn 1',text)
        self.assertIn('Cwire0 wire_dn VGND 2f',text)
        self.assertTrue(mapping['first_sync_input_loads_included'])
        self.assertFalse(mapping['sync_clock_tree_RC_included'])

    def test_wrong_wire_value_master_or_multiple_sink_rejected(self):
        f=list(fixture());f[2]['networks'][0]['resistors'][0]['ohms']='3'
        with self.assertRaises(ValueError):extend(*f)
        f=list(fixture());f[3]['cells']['dn']['type']='sky130_fd_sc_hs__dfrtp_2'
        with self.assertRaises(ValueError):extend(*f)
        f=list(fixture());f[2]['networks'][0]['outside_terminals']*=2
        with self.assertRaises(ValueError):extend(*f)


if __name__=='__main__':unittest.main()
