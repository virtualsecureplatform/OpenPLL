import unittest
from inventory_prototype_context_interfaces import lef_directions, obligations


class InterfaceDirectionTests(unittest.TestCase):
    def test_external_macro_polarity(self):
        def endpoint(role, direction):
            return dict(role=role, direction=direction)
        self.assertEqual(obligations([endpoint('digital', 'OUTPUT')]), 'external_driver_required')
        self.assertEqual(obligations([endpoint('digital', 'INPUT'), endpoint('oscillator', 'OUTPUT')]),
                         'receiver_devices_and_loading_required')
        self.assertEqual(obligations([endpoint('digital', 'INPUT'), endpoint('detector', 'OUTPUT')]),
                         'external_driver_and_receiver_loading_required')
        self.assertEqual(obligations([]), 'unresolved_or_bidirectional')
        self.assertEqual(obligations([endpoint('digital', 'INOUT')]), 'unresolved_or_bidirectional')

    def test_physical_pin_parser_rejects_incomplete_direction(self):
        self.assertEqual(lef_directions('PIN CLK\n DIRECTION INPUT ;\n PORT\n END\nEND CLK'), {'CLK': 'INPUT'})
        for text in ('PIN CLK\nEND CLK', 'PIN CLK\nDIRECTION INPUT ;',
                     'PIN CLK\nDIRECTION INPUT ;\nDIRECTION OUTPUT ;\nEND CLK'):
            with self.assertRaises(ValueError):
                lef_directions(text)


if __name__ == '__main__':
    unittest.main()
