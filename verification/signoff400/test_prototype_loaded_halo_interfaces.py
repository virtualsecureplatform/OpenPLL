import unittest
from resolve_prototype_loaded_halo_interfaces import library_directions, local_bindings, obligations


class LoadedHaloInterfaces(unittest.TestCase):
    def test_library_keeps_repeated_pin_names_separate_by_master(self):
        text = ('MACRO A\n PIN X\n DIRECTION INPUT ;\n END X\nEND A\n'
                'MACRO B\n PIN X\n DIRECTION OUTPUT ;\n END X\nEND B\n')
        self.assertEqual(library_directions(text), {'A': {'X': 'INPUT'}, 'B': {'X': 'OUTPUT'}})
        with self.assertRaises(ValueError):
            library_directions(text.replace('END B', 'END wrong'))

    def test_exact_local_aliases_bind_physical_pins_and_reject_conflicts(self):
        instances = [dict(instance='p', leaf_master='Cell', local_primitive_signature=['model', ['A', 'internal'], []]),
                     dict(instance='q', leaf_master='Cell', local_primitive_signature=['model', ['AA', 'other'], []])]
        models = {'Cell': (['A'], [('alias', 'A', 'AA')])}
        bound, alias = local_bindings(instances, {'p': ['x', 'y'], 'q': ['x', 'z']}, {'p': 'placed1', 'q': 'placed1'}, models)
        self.assertEqual(bound['placed1']['nodes'][alias['Cell'].find('A')], 'x')
        with self.assertRaises(ValueError):
            local_bindings(instances, {'p': ['x', 'y'], 'q': ['wrong', 'z']}, {'p': 'placed1', 'q': 'placed1'}, models)

    def test_driver_receiver_primary_and_unknown_obligations_are_explicit(self):
        endpoints = [dict(side='outside', direction='OUTPUT'), dict(side='outside', direction='INPUT')]
        self.assertEqual(set(obligations(endpoints, set())),
                         {'external_cell_driver_waveform_required', 'external_cell_receiver_loading_required'})
        self.assertIn('primary_input_waveform_required', obligations([dict(side='inside', direction='INPUT')], {'INPUT'}))
        self.assertIn('driver_origin_unresolved', obligations([], set()))


if __name__ == '__main__':
    unittest.main()
