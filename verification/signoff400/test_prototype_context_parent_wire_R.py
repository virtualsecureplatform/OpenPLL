from copy import deepcopy
from fractions import Fraction as F
import unittest
from build_prototype_context_parent_wire_R import source_inventory, plan, render, contraction_review


class ParentWireLift(unittest.TestCase):
    def fixture(self):
        source = ['.subckt Top OUT gate drain',
                  'Xflat0 OUT gate 0 0 sky130_fd_pr__nfet_01v8 w=1 l=0.15',
                  'Xflat1 drain OUT 0 0 sky130_fd_pr__nfet_01v8 w=1 l=0.15',
                  'Cflat0 OUT 0 1e-15', 'Cflat1 OUT gate -1e-20', '.ends Top']
        nets = [dict(net='a', context_conductor='OUT',
                     terminals=[dict(node='OUT', kind='P', direction='O'), dict(node='macro:A', kind='I', direction='O')],
                     resistors=[dict(nodes=['OUT', 'macro:A'], ohms='2')]),
                dict(net='b', context_conductor='OUT',
                     terminals=[dict(node='macro:B', kind='I', direction='O'), dict(node='load:A', kind='I', direction='I')],
                     resistors=[dict(nodes=['macro:B', 'load:A'], ohms='3')])]
        bindings = [dict(net='a', wire_terminal='OUT', context_conductor='OUT', ideal_supply_boundary=False, top_port=True, primitive_terminal_positions=[])]
        for net, token, position in [('a', 'macro:A', ['Xflat0', 0]), ('b', 'macro:B', ['Xflat0', 0]), ('b', 'load:A', ['Xflat1', 1])]:
            bindings.append(dict(net=net, wire_terminal=token, context_conductor='OUT', ideal_supply_boundary=False,
                                 top_port=False, primitive_terminal_positions=[position]))
        return source, nets, bindings

    def test_shared_access_and_signed_C_round_trip(self):
        source, nets, bindings = self.fixture()
        terminals, nodes, ports = source_inventory(source)
        variants = []
        for attachment in ('driver', 'farthest'):
            p = plan(nets, bindings, terminals, nodes, ports, {'0'}, attachment)
            emitted = render(source, p)
            self.assertTrue(contraction_review(source, emitted, p)['all_primitive_and_signed_C_cards_recovered_by_R_contraction'])
            self.assertEqual(len(p['shared_junctions']), 1)
            self.assertEqual(len(p['wire']), 2)
            self.assertTrue(all(r[3] > 0 for r in p['wire']))
            self.assertTrue(any('-1e-20' in line for line in emitted))
            expected = p['positions']['Xflat0', 0] if attachment == 'driver' else p['positions']['Xflat1', 1]
            self.assertEqual(p['anchors']['OUT'], expected)
            variants.append(p['anchors']['OUT'])
        self.assertNotEqual(*variants)

    def test_missing_incidence_and_changed_export_fail(self):
        source, nets, bindings = self.fixture()
        terms, nodes, ports = source_inventory(source)
        with self.assertRaises(ValueError):
            plan(nets, bindings[:-1], terms, nodes, ports, {'0'}, 'driver')
        p = plan(nets, bindings, terms, nodes, ports, {'0'}, 'driver')
        emitted = render(source, p)
        changed = [line.replace('w=1', 'w=2') for line in emitted]
        with self.assertRaises(ValueError):
            contraction_review(source, changed, p)
        changed = [line for line in emitted if not line.startswith('RparentWire0 ')]
        with self.assertRaises(ValueError):
            contraction_review(source, changed, p)

    def test_nonpositive_wire_and_incomplete_source_coverage_fail(self):
        source, nets, bindings = self.fixture()
        terms, nodes, ports = source_inventory(source)
        bad = deepcopy(nets); bad[0]['resistors'][0]['ohms'] = '0'
        with self.assertRaises(ValueError):
            plan(bad, bindings, terms, nodes, ports, {'0'}, 'driver')
        terms['extra'] = ['OUT']
        with self.assertRaises(ValueError):
            plan(nets, bindings, terms, nodes, ports, {'0'}, 'driver')

    def test_ideal_supply_remains_fixed_without_adopting_supply_wire_R(self):
        source, nets, bindings = self.fixture()
        source[0] += ' VNB'
        source.insert(-1, 'Cflat2 VNB OUT 2e-20')
        nets.append(dict(net='VNB', context_conductor='VNB',
                         terminals=[dict(node='VNB', kind='P', direction='I')],
                         resistors=[dict(nodes=['VNB', 'macro:VNB'], ohms='50')]))
        bindings.append(dict(net='VNB', wire_terminal='VNB', context_conductor='VNB',
                             ideal_supply_boundary=True, top_port=True, primitive_terminal_positions=[]))
        terms, nodes, ports = source_inventory(source)
        p = plan(nets, bindings, terms, nodes, ports, {'0', 'VNB'}, 'driver')
        emitted = render(source, p)
        self.assertEqual(len(p['wire']), 2)
        self.assertNotIn('VNB', p['anchors'])
        self.assertTrue(any(line.startswith('Cflat2 VNB ') for line in emitted))
        contraction_review(source, emitted, p)


if __name__ == '__main__':
    unittest.main()
