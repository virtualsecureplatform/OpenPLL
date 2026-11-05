import unittest
from check_prototype_gate_connectivity import screen


def mos(d,g,s):return ('sky130_fd_pr__nfet_01v8',(d,g,s,'VGND'),())


class GateConnectivityControls(unittest.TestCase):
    def test_gate_only_net_is_not_a_DC_driver(self):
        r=screen({mos('out','floating','VGND'):1},set())
        self.assertEqual(r['unsupported_gate_conductors'][0]['node'],'floating')
        self.assertFalse(r['all_gate_conductors_have_potential_DC_support'])

    def test_channel_chain_and_external_input_support_are_retained(self):
        r=screen({mos('out','INPUT','middle'):1,mos('middle','VGND','VGND'):1,mos('out2','out','VGND'):1},{'INPUT'})
        self.assertTrue(r['all_gate_conductors_have_potential_DC_support'])
        self.assertFalse(r['all_bias_states_and_voltage_stress_qualified'])


if __name__=='__main__':unittest.main()
