import unittest
from trace_CDC_interstage_paths import trace
from test_mapped_CDC_inventory import fixture


class InterstagePathControls(unittest.TestCase):
    def routed(self,kinds):
        m=fixture();bit=4
        for i,kind in enumerate(kinds):
            out=20+i;m['cells']['b'+str(i)]=dict(type='sky130_fd_sc_hs__'+kind+'_2',
                port_directions=dict(A='input',X='output'),connections=dict(A=[bit],X=[out]));bit=out
        m['cells']['sync']['connections']['D']=[bit]
        return m

    def test_direct_buffered_and_even_inverting_paths_are_traced_in_signal_order(self):
        for kinds in ((),('clkbuf','buf'),('inv','clkinv')):
            with self.subTest(kinds=kinds):
                result=trace(self.routed(kinds),'meta','sync')
                self.assertEqual([c['routed_cell'] for c in result['intermediate_cells']],['b'+str(i) for i in range(len(kinds))])
                self.assertEqual(result['inversion_parity'],0)

    def test_odd_inversion_gate_cycle_and_wrong_source_rejected(self):
        for fault in ('inversion','gate','cycle','source'):
            with self.subTest(fault=fault):
                m=self.routed(('inv',) if fault=='inversion' else ('buf',))
                if fault=='gate':m['cells']['b0']['type']='sky130_fd_sc_hs__and2_1'
                if fault=='cycle':m['cells']['b0']['connections']['A']=[20]
                if fault=='source':m['cells']['b0']['connections']['A']=[3]
                with self.assertRaises(ValueError):trace(m,'meta','sync')


if __name__=='__main__':unittest.main()
