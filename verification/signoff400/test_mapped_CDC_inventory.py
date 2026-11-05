import copy
import unittest
from inventory_mapped_CDC import inventory


def fixture():
    def ff(clock,data,q):return dict(type='sky130_fd_sc_hs__dfrtp_1',port_directions=dict(CLK='input',D='input',Q='output',RESET_B='input'),
                                     connections=dict(CLK=[clock],D=[data],Q=[q],RESET_B=[2]))
    return dict(ports={n:dict(direction='input',bits=[b]) for n,b in [('clk_a',1),('reset_n',2),('clk_b',5),('enable',8)]},
        netnames={'marked_pair':dict(bits=[4,7],attributes={'ASYNC_REG':'TRUE'}),'unmarked':dict(bits=[3],attributes={})},
        cells={'source':ff(1,'0',3),'meta':ff(5,6,4),'sync':ff(5,4,7),
               'gate':dict(type='sky130_fd_sc_hs__and2_1',port_directions=dict(A='input',B='input',X='output'),
                           connections=dict(A=[3],B=[8],X=[6]))})


class MappedCDCControls(unittest.TestCase):
    def test_exhaustive_data_and_reset_cones_include_unmarked_sources(self):
        result=inventory(fixture())
        self.assertEqual(result['sequential_cells'],3)
        self.assertEqual(len(result['data_crossing_candidates']),1)
        crossing=result['data_crossing_candidates'][0]
        self.assertEqual(crossing['destination_cell'],'meta')
        self.assertEqual({s['name'] for s in crossing['sources']},{'enable','source'})
        self.assertEqual(len(result['asynchronous_control_groups']),2)
        self.assertEqual(result['directly_connected_marked_two_stage_chains'][0]['first_cell'],'meta')
        self.assertFalse(result['complete_structural_inventory_qualified'])
        self.assertFalse(result['physical_CDC_qualified'])

    def test_missing_driver_cycle_unknown_cell_and_duplicate_driver_rejected(self):
        for fault in ('missing','cycle','unreviewed_sequential','duplicate','unknown_logic'):
            with self.subTest(fault=fault):
                m=copy.deepcopy(fixture())
                if fault=='missing':m['cells']['gate']['connections']['A']=[99]
                if fault=='cycle':m['cells']['gate']['connections']['A']=[6]
                if fault=='unreviewed_sequential':m['cells']['source']['type']='sky130_fd_sc_hs__dlxtp_1'
                if fault=='duplicate':m['cells']['gate']['connections']['X']=[3]
                if fault=='unknown_logic':m['cells']['source']['connections']['D']=['x']
                with self.assertRaises(ValueError):inventory(m)


if __name__=='__main__':unittest.main()
