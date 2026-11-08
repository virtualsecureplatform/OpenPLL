import copy
import unittest
from run_keeper_static_terminated_DCO import environment


class StaticEnvironment(unittest.TestCase):
    def fixture(self):
        driven = {'VPWR': 'p', 'VPB': 'b', 'VGND': 'g', 'VNB': 'n',
                  'DCO_native.RESET_N': 'reset', 'receiver': 'rx', 'exterior': 'ext'}
        roles = []
        observations = {}
        for bus, count in [('COARSETHERMAL_CODE', 47), ('DCO_THERM', 255)]:
            for bit in range(count):
                node = f'{bus}_{bit}'
                driven[node] = 's_' + node
                observations[node] = dict(endpoint='macro', physical_node=node, bus=bus, bit=bit)
        for node in driven:
            kind = 'retained_primitive_terminal' if node in observations or node in ('DCO_native.RESET_N', 'receiver') else 'capacitive_only'
            roles.append(dict(node=node, kind=kind, terminal_roles=['MOS_diffusion'] if node == 'receiver' else []))
        return dict(externally_driven_ports=driven, observation_only_ports={'PLLOUT': 'out'}), roles, observations

    def test_static_truth_table_and_free_outputs(self):
        bindings, roles, observations = self.fixture()
        mapping, reset, receiver = environment(bindings, roles, observations, 20, 149)
        self.assertEqual(mapping['s_COARSETHERMAL_CODE_19'], 'VDD')
        self.assertEqual(mapping['s_COARSETHERMAL_CODE_20'], '0')
        self.assertEqual(mapping['s_DCO_THERM_148'], '0')
        self.assertEqual(mapping['s_DCO_THERM_149'], 'VDD')
        self.assertEqual(mapping['ext'], '0')
        self.assertEqual(mapping['reset'], 'RESET_DRIVER')
        self.assertEqual(mapping['rx'], 'RECEIVER')
        self.assertEqual(mapping['out'], 'PLLOUT')
        self.assertEqual(reset, 'DCO_native.RESET_N')
        self.assertEqual(receiver, 'receiver')

    def test_missing_or_duplicate_role_rejected(self):
        b, r, o = self.fixture()
        for bad in [r[:-1], r + [copy.deepcopy(r[0])]]:
            with self.assertRaises(ValueError):
                environment(b, bad, o, 20, 149)

    def test_unhandled_active_boundary_rejected(self):
        b, r, o = self.fixture()
        next(row for row in r if row['node'] == 'exterior')['kind'] = 'retained_primitive_terminal'
        with self.assertRaises(ValueError):
            environment(b, r, o, 20, 149)

    def test_missing_programming_bit_and_invalid_code_rejected(self):
        b, r, o = self.fixture()
        for coarse, fine in [(48,149), (20,7), (20,248), (True,149)]:
            with self.assertRaises(ValueError):
                environment(b,r,o,coarse,fine)
        o.pop(next(iter(o)))
        with self.assertRaises(ValueError):
            environment(b,r,o,20,149)


if __name__ == '__main__':
    unittest.main()
