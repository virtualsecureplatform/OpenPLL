from copy import deepcopy
import unittest
from bind_prototype_child_wire_primitives import match, unescape
from compare_prototype_physical_primitive_graphs import Union


class ChildPrimitiveMapping(unittest.TestCase):
    def fixture(self):
        identity = (('Child', 'scale 1000 1 500000', ('inv', 1, 0, 10, 0, 1, 20)),)
        signature = ('sky130_fd_pr__nfet_01v8', ('Y', 'A', 'S', 'B'), (('l', '3/20'),))
        physical = (identity, 'inv', signature, 0)
        primitives = {physical: (signature[0], ('Child/net', 'A', '0', '0'), signature[2])}
        metadata = dict(physical_instances=[dict(instance='Xflat5',
            physical_hierarchy_identity=(('Parent', 'scale 1000 1 500000', ('Child', 1, 0, 90, 0, 1, 20)),) + identity,
            leaf_master='inv', local_primitive_signature=signature, parallel_ordinal=0)])
        return primitives, metadata

    def test_physical_paths_not_counters_and_named_ports(self):
        primitives, metadata = self.fixture()
        mapping, paired = match(primitives, Union(), metadata, {'Xflat5': ['out', 'input', '0', '0']},
                                'Child', {'A': 'input'})
        self.assertEqual(mapping['Child/net'], 'out')
        self.assertEqual(mapping['A'], 'input')
        self.assertEqual(len(paired), 1)
        with self.assertRaises(ValueError):
            match(primitives, Union(), metadata, {'Xflat5': ['out', 'input', '0', '0']}, 'Child', {'A': 'wrong'})

    def test_changed_placement_or_primitive_card_rejected(self):
        primitives, metadata = self.fixture()
        for change in ('placement', 'card'):
            wrong = deepcopy(metadata); row = wrong['physical_instances'][0]
            if change == 'placement':
                row['physical_hierarchy_identity'] = row['physical_hierarchy_identity'][:1] + (
                    ('Child', 'scale 1000 1 500000', ('inv', 1, 0, 11, 0, 1, 20)),)
            else:
                row['leaf_master'] = 'different'
            with self.assertRaises(ValueError):
                match(primitives, Union(), wrong, {'Xflat5': ['out', 'input', '0', '0']}, 'Child', {'A': 'input'})

    def test_escaped_names_without_replacement_string_escapes(self):
        self.assertEqual(unescape(chr(92) + 'a' + chr(92) + '[2' + chr(92) + ']'), 'a[2]')
        with self.assertRaises(ValueError):
            unescape('a' + chr(92))


if __name__ == '__main__':
    unittest.main()
