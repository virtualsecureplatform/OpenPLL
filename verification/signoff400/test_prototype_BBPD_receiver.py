import copy
import unittest
from prepare_prototype_BBPD_receiver_v2 import select
from run_prototype_BBPD_receiver_pilot import read_table


def fixture():
    def flop(clock,data,q):
        return dict(type='sky130_fd_sc_hs__dfrtp_1',connections={'CLK':[clock],'D':[data],'Q':[q],'RESET_B':[3]},port_directions={'CLK':'input','D':'input','Q':'output','RESET_B':'input'})
    def inverter(a,y):return dict(type='sky130_fd_sc_hs__inv_1',connections={'A':[a],'Y':[y]},port_directions={'A':'input','Y':'output'})
    module=dict(ports={'BBPD':{'direction':'input','bits':[1,2]},'ENABLE':{'direction':'input','bits':[3]}},
        netnames={},cells={'f0':flop(1,4,5),'f1':flop(2,7,8),'i0':inverter(5,4),'i1':inverter(8,7)})
    states=[dict(cell='f0',clock_bit=1),dict(cell='f1',clock_bit=2)]
    return module,states


class ReceiverConeIntegrity(unittest.TestCase):
    def test_feedback_cones_stop_at_event_flop_and_keep_boundary_controls(self):
        m,s=fixture();r=select(m,s)
        self.assertEqual(set(r['cells']),{'f0','f1','i0','i1'})
        self.assertEqual({b['bit'] for b in r['boundaries']},{1,2,3})
        self.assertEqual({x['bit'] for x in r['event_outputs']},{5,8})

    def test_missing_and_multiple_drivers_are_rejected(self):
        m,s=fixture();del m['cells']['i0']
        with self.assertRaisesRegex(ValueError,'driver'):select(m,s)
        m,s=fixture();m['cells']['duplicate']=copy.deepcopy(m['cells']['i0'])
        with self.assertRaisesRegex(ValueError,'driver'):select(m,s)

    def test_native_receiver_table_cannot_be_truncated(self):
        text='No. of Data Rows : 2\n0 0 0 0 0 0\n1 8e-8 0 0 0 0\n'
        self.assertEqual(len(read_table(text)),2)
        for bad in (text.replace('8e-8','7e-8'),text.replace('1 8e-8','2 8e-8')):
            with self.assertRaises(ValueError):read_table(bad)


if __name__=='__main__':unittest.main()
