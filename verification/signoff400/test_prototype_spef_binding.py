import copy
import unittest
from prototype_spef_v2 import parse
from bind_prototype_spef_pins_v2 import bind
from test_prototype_spef import FIXTURE

SOURCE='.subckt leaf A Z\n.ends\n.subckt top input output\nXphysical input output leaf\n.ends\n'


class SPEFBindingControls(unittest.TestCase):
    def test_physical_instance_mapping_and_connected_terminals(self):
        result=bind(parse(FIXTURE),SOURCE,'top',{'cell':'physical'})
        self.assertTrue(result['all_RC_terminals_bound_and_connected'])
        self.assertEqual(result['networks'][0]['logical_nodes'],['input'])

    def test_wrong_pin_mapping_and_disconnected_resistance_do_not_pass(self):
        for fault in ('pin','instance','disconnected'):
            with self.subTest(fault=fault):
                spef=parse(FIXTURE);mapping={'cell':'physical'}
                if fault=='pin':spef['nets'][0]['connections'][1]['node']='cell:Z'
                if fault=='instance':mapping={}
                if fault=='disconnected':spef['nets'][0]['resistors']=[]
                self.assertFalse(bind(spef,SOURCE,'top',mapping)['all_RC_terminals_bound_and_connected'])


if __name__=='__main__':unittest.main()
