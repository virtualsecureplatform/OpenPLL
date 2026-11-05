"""Topology guards for the joint destination-control proof abstraction."""
import unittest

from verify_handoff_control import extract


class ControlExtractionTests(unittest.TestCase):
    def setUp(self):
        self.states = {'remaining': ['r0', 'r1'], 'transfer_busy': ['busy'],
                       'capture_pending': ['capture'], 'pending_request': ['pending'],
                       'acknowledge': ['ack']}
        cells = {}
        for index, name in enumerate(['r0', 'r1', 'busy', 'capture', 'pending', 'ack', 'request']):
            cells[name] = {'type': 'sky130_fd_sc_hs__dfrtp_1', 'parameters': {},
                           'attributes': {}, 'connections': {'CLK': [2], 'RESET_B': [3],
                                                            'D': [16], 'Q': [10 + index]}}
        ff = {'ports': {'CLK': {'direction': 'input'}, 'RESET_B': {'direction': 'input'},
                        'D': {'direction': 'input'}, 'Q': {'direction': 'output'}}}
        inv = {'ports': {'A': {'direction': 'input'}, 'Y': {'direction': 'output'}}}
        self.design = {'modules': {'IntegerPLL_AcquiringCore': {'ports': {
            'PLLOUT': {'direction': 'input', 'bits': [2]},
            'RESET_N': {'direction': 'input', 'bits': [3]},
            'OTHER_RESET_N': {'direction': 'input', 'bits': [4]}}, 'cells': cells},
            'sky130_fd_sc_hs__dfrtp_1': ff, 'sky130_fd_sc_hs__inv_1': inv}}

    def test_keeps_all_state_and_cuts_only_request(self):
        reduced, contract = extract(self.design, self.states, 'request', 'gate')
        module = reduced['modules']['gate_control']
        self.assertEqual(module['ports']['STATE']['bits'], list(range(10, 16)))
        self.assertEqual(module['ports']['REQUEST_SYNC']['bits'], [16])
        self.assertEqual(set(module['cells']), {'r0', 'r1', 'busy', 'capture', 'pending', 'ack'})
        self.assertEqual(contract['clock_origin'], ['port', 'PLLOUT', 0, 0])

    def add_passive_diode(self):
        self.design['modules']['sky130_fd_sc_hs__diode_2'] = {
            'ports': {'DIODE': {'direction': 'input'}}}
        self.design['modules']['IntegerPLL_AcquiringCore']['cells']['antenna'] = {
            'type': 'sky130_fd_sc_hs__diode_2', 'connections': {'DIODE': [15]}}

    def test_passive_diode_does_not_drive_control_state(self):
        self.add_passive_diode()
        reduced, contract = extract(self.design, self.states, 'request', 'gate')
        self.assertNotIn('antenna', reduced['modules']['gate_control']['cells'])
        self.assertEqual(contract['state_bits'], 6)

    def test_diode_with_uncharacterized_output_is_rejected(self):
        self.add_passive_diode()
        self.design['modules']['IntegerPLL_AcquiringCore']['cells']['antenna']['connections']['Y'] = [15]
        with self.assertRaisesRegex(RuntimeError, 'Uncharacterized cell ports'):
            extract(self.design, self.states, 'request', 'gate')

    def test_rejects_inverted_destination_clock(self):
        cells = self.design['modules']['IntegerPLL_AcquiringCore']['cells']
        cells['clock_inv'] = {'type': 'sky130_fd_sc_hs__inv_1',
                              'connections': {'A': [2], 'Y': [30]}}
        cells['ack']['connections']['CLK'] = [30]
        with self.assertRaisesRegex(RuntimeError, 'clock/reset mismatch'):
            extract(self.design, self.states, 'request', 'gate')

    def test_rejects_independent_control_reset(self):
        self.design['modules']['IntegerPLL_AcquiringCore']['cells']['pending']['connections']['RESET_B'] = [4]
        with self.assertRaisesRegex(RuntimeError, 'clock/reset mismatch'):
            extract(self.design, self.states, 'request', 'gate')

    def test_rejects_unmodeled_register_boundary(self):
        cells = self.design['modules']['IntegerPLL_AcquiringCore']['cells']
        cells['extra'] = {'type': 'sky130_fd_sc_hs__dfrtp_1',
                          'connections': {'CLK': [2], 'RESET_B': [3], 'D': [16], 'Q': [30]}}
        cells['ack']['connections']['D'] = [30]
        with self.assertRaisesRegex(RuntimeError, 'Unexpected register'):
            extract(self.design, self.states, 'request', 'gate')

    def test_rejects_export_alias_short_outside_control_cone(self):
        cells = self.design['modules']['IntegerPLL_AcquiringCore']['cells']
        for name in ('original_output_driver', 'buffered_output_driver'):
            cells[name] = {'type': 'sky130_fd_sc_hs__inv_1',
                           'connections': {'A': [16], 'Y': [90]}}
        with self.assertRaisesRegex(RuntimeError, 'Multiple drivers on 90'):
            extract(self.design, self.states, 'request', 'gate')


if __name__ == '__main__':
    unittest.main()
