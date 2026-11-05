import copy
import unittest
from map_prototype_receiver_aggressors import resolve


def fixture():
    model={'off_network_aggressors':[{'spef_node':'wire:1','port':'aggressor_0'}]}
    bound={'networks':[{'net':'victim','logical_bit':3,'capacitors':[
        {'nodes':['victim:1','wire:1'],'farads':'1/1000000000000000'}]}]}
    spef={'nets':[{'name':'aggressor','connections':[
        {'kind':'P','node':'CONFIG[5]','direction':'I'},
        {'kind':'I','node':'buffer:A','direction':'I'}],
        'resistors':[{'nodes':['CONFIG[5]','wire:1']},{'nodes':['wire:1','buffer:A']}],
        'capacitors':[]}]}
    module={'ports':{'CONFIG':{'direction':'input','bits':[1,2],'offset':4}},
            'netnames':{'CONFIG':{'bits':[1,2]}},'cells':{
                'buffer':{'type':'sky130_fd_sc_hs__buf_1','connections':{'A':[2],'X':[4]},
                          'port_directions':{'A':'input','X':'output'}}}}
    return model,bound,spef,module


class AggressorOwnership(unittest.TestCase):
    def test_vector_primary_driver_and_actual_cone(self):
        rows=resolve(*fixture())
        self.assertEqual(rows[0]['logical_bit'],2)
        self.assertEqual(rows[0]['drivers'],[{'primary_input':'CONFIG','index':1}])
        self.assertEqual(rows[0]['source_origins'],(('primary','CONFIG',1),))
        self.assertEqual(rows[0]['victim_couplings'][0]['victim_bit'],3)

    def test_unbound_or_ambiguous_ownership_rejected(self):
        f=fixture();f[2]['nets'][0]['resistors']=[]
        with self.assertRaises(ValueError):resolve(*f)
        f=fixture();other=copy.deepcopy(f[2]['nets'][0]);other['name']='other';f[2]['nets'].append(other)
        with self.assertRaises(ValueError):resolve(*f)

    def test_selected_network_and_multiple_drivers_rejected(self):
        f=fixture();f[1]['networks'][0]['net']='aggressor'
        with self.assertRaises(ValueError):resolve(*f)
        f=fixture();f[2]['nets'][0]['connections'].append({'kind':'I','node':'buffer:X','direction':'O'})
        with self.assertRaises(ValueError):resolve(*f)


if __name__=='__main__':unittest.main()
