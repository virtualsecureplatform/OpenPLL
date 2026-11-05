import unittest
from inventory_prototype_interface_loading import inventory

SOURCE = '''.subckt analog OUT VPWR
+ VGND
X0 OUT OUT VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=1
Cinside OUT VGND 9f
.ends
.subckt receiver A VDD VSS
X0 Z A VSS VSS sky130_fd_pr__nfet_01v8 l=0.15 w=0.5
Cpin A VSS 2f
.ends
.subckt top OUT VDD VSS
Xanalog OUT VDD VSS analog
Xreceiver OUT VDD VSS receiver
Cwire OUT VSS 3f
Ccouple OUT aggressor -0.5f
.ends
'''


class InterfaceLoadingControls(unittest.TestCase):
    def test_analog_self_loading_excluded_and_external_gate_retained(self):
        r = inventory(SOURCE, 'top', 'analog', 'OUT')
        self.assertEqual(r['external_primitive_instances'], 1)
        self.assertEqual(r['external_primitive_terminals'][0]['incident_terminals'], ['gate'])
        caps = {tuple(c['nodes']): c['farads'] for c in r['incident_signed_capacitances']}
        self.assertEqual(caps[('OUT', 'VSS')], '1/200000000000000')
        self.assertEqual(caps[('OUT', 'top/aggressor')], '-1/2000000000000000')
        self.assertFalse(r['intrinsic_device_capacitance_evaluated'])
        self.assertFalse(r['parent_loading_complete'])

    def test_duplicate_target_rejected(self):
        with self.assertRaisesRegex(ValueError, 'one direct'):
            inventory(SOURCE.replace('Xanalog OUT', 'Xother OUT VDD VSS analog\nXanalog OUT'),
                      'top', 'analog', 'OUT')


if __name__ == '__main__':
    unittest.main()
