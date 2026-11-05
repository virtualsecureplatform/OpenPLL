from copy import deepcopy
import unittest
from build_prototype_context_hierarchical_wire_R import combine, plan
from build_prototype_context_parent_wire_R import source_inventory, render, contraction_review


class HierarchicalWireJunctions(unittest.TestCase):
    def fixture(self):
        source = ['.subckt Top A Y',
                  'Xflat0 Y A 0 0 sky130_fd_pr__nfet_01v8 l=0.15 w=1',
                  'Cflat0 A 0 1e-15', '.ends Top']
        parent = [dict(net='input', context_conductor='A',
                       terminals=[dict(node='A', kind='P', direction='I', cell_model=None),
                                  dict(node='macro:IN', kind='I', direction='I', cell_model='Child')],
                       resistors=[dict(nodes=['A', 'macro:IN'], ohms='2')])]
        rows = [dict(net='input', wire_terminal='A', context_conductor='A', ideal_supply_boundary=False,
                     top_port=True, primitive_terminal_positions=[]),
                dict(net='input', wire_terminal='macro:IN', context_conductor='A', ideal_supply_boundary=False,
                     top_port=False, primitive_terminal_positions=[['Xflat0', 1]])]
        child = [dict(net='IN', context_conductor='A',
                      terminals=[dict(node='IN', kind='P', direction='I', context_conductor='A', ideal_supply_boundary=False,
                                      primitive_terminal_positions=[],
                                      parent_access=dict(parent_net='input', parent_wire_terminal='macro:IN')),
                                 dict(node='cell:A', kind='I', direction='I', context_conductor='A', ideal_supply_boundary=False,
                                      primitive_terminal_positions=[['Xflat0', 1]])],
                      resistors=[dict(nodes=['IN', 'cell:A'], ohms='3')])]
        return source, parent, rows, child

    def test_parent_child_boundary_is_not_a_leaf_or_ideal_input_driver(self):
        source, parent, rows, child = self.fixture()
        nets, bindings, aliases = combine(parent, rows, child, 'Child')
        terms, nodes, ports = source_inventory(source)
        p = plan(nets, bindings, terms, nodes, ports, {'0'}, 'driver', aliases)
        self.assertEqual(p['anchors']['A'], 'A')
        self.assertEqual(len(p['wire']), 2)
        self.assertEqual(len(p['positions']), 1)
        self.assertNotEqual(p['positions']['Xflat0', 1], 'A')
        contraction_review(source, render(source, p), p)
        far = plan(nets, bindings, terms, nodes, ports, {'0'}, 'farthest', aliases)
        self.assertEqual(far['anchors']['A'], far['positions']['Xflat0', 1])

    def test_missing_duplicate_or_wrong_junction_fails(self):
        source, parent, rows, child = self.fixture()
        nets, bindings, aliases = combine(parent, rows, child, 'Child')
        terms, nodes, ports = source_inventory(source)
        for wrong in ([], aliases + aliases, [(aliases[0][0], ('child::IN', 'cell:A'))]):
            with self.assertRaises(ValueError):
                plan(nets, bindings, terms, nodes, ports, {'0'}, 'driver', wrong)

    def test_original_proofs_are_not_mutated(self):
        _, parent, rows, child = self.fixture()
        before = deepcopy((parent, rows, child))
        combine(parent, rows, child, 'Child')
        self.assertEqual((parent, rows, child), before)


if __name__ == '__main__':
    unittest.main()
