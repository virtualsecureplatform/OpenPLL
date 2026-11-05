import unittest
from inventory_prototype_loaded_domain_halo import select


class LoadedDomainHalo(unittest.TestCase):
    def test_selects_complete_incident_driver_and_receiver_cells(self):
        terms = {'inside': ['x', '0'], 'driver': ['x', 'u', 'VDD'],
                 'driver_internal': ['u', 'v'], 'receiver': ['x', 'z'],
                 'next_hop': ['u', 'w'], 'far': ['VDD', 'q']}
        cells = {'inside': 'base', 'driver': 'D', 'driver_internal': 'D',
                 'receiver': 'R', 'next_hop': 'N', 'far': 'F'}
        expanded, cuts, private, remaining = select(terms, cells, {'inside'}, {'0', 'VDD'})
        self.assertEqual(expanded, {'inside', 'driver', 'driver_internal', 'receiver'})
        self.assertEqual(cuts, {'x'})
        self.assertIn('x', private)
        self.assertEqual(remaining, {'u'})
        self.assertNotIn('far', expanded)

    def test_rejects_missing_physical_cell_or_unknown_base_primitive(self):
        with self.assertRaises(ValueError):
            select({'a': ['x']}, {}, {'a'}, set())
        with self.assertRaises(ValueError):
            select({'a': ['x']}, {'a': 'cell'}, {'missing'}, set())


if __name__ == '__main__':
    unittest.main()
