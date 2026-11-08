import unittest
from audit_keeper_replay_causality import inventory


class ReplayCausality(unittest.TestCase):
    def fixture(self):
        text = '.subckt plant out ctrl forced vdd\nXone forced out vdd vdd __openpll_leaf\nXtwo out ctrl vdd vdd __openpll_leaf\n.ends plant\n'
        bindings = dict(externally_driven_ports={'CODE': 'ctrl', 'receiver': 'forced', 'VPWR': 'vdd'}, observation_only_ports={'PLLOUT': 'out'})
        observations = {'CODE.macro': dict(endpoint='macro', physical_node='CODE')}
        return text, bindings, observations

    def test_forced_receiver_is_detected_without_clamping_output(self):
        result = inventory(*self.fixture())
        self.assertEqual(result['role_counts'], {'other_prescribed_boundary': 1, 'programming_macro_endpoint': 1, 'supply': 1})
        self.assertEqual(result['observed_gate_to_prescribed_terminal_calls'][0]['prescribed_terminal'], 'receiver')
        self.assertFalse(result['changed_controller_prediction_qualified'])

    def test_supply_is_not_reported_as_receiver_feedback(self):
        text, bindings, observations = self.fixture()
        result = inventory(text.replace('Xone forced out', 'Xone vdd out'), bindings, observations)
        self.assertEqual(result['observed_gate_to_prescribed_terminal_calls'], [])

    def test_missing_physical_control_rejected(self):
        text, bindings, observations = self.fixture()
        del bindings['externally_driven_ports']['CODE']
        with self.assertRaises(ValueError):
            inventory(text, bindings, observations)


if __name__ == '__main__':
    unittest.main()
