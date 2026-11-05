import unittest
from link_outside_device_bindings import classify


class OutsideDeviceBindings(unittest.TestCase):
    def endpoint(self):
        return dict(group='1', private_id='_rmesh_1_a', conductor='same_label', creation_point=[1, 2])

    def binding(self):
        return dict(native_group_id='1', private_id='_rmesh_1_a', original_conductor='same_label',
                    point_internal=[9, 2], terminal=2)

    def test_device_location_difference_never_relocates_endpoint(self):
        e, b = self.endpoint(), self.binding()
        result = classify(e, [b, b])
        self.assertEqual(result['association'], 'same_private_node_different_device_location')
        self.assertEqual(len(result['device_bindings']), 2)
        self.assertEqual(result['endpoint']['creation_point'], [1, 2])
        self.assertFalse(result['endpoint_relocated'])
        self.assertFalse(result['physical_interface_qualified'])
        b['point_internal'] = [1, 2]
        self.assertEqual(classify(e, [b])['exact_device_location_count'], 1)
        self.assertEqual(classify(e, [])['association'], 'no_device_binding')

    def test_cross_snapshot_private_identity_and_unknown_terminal_fail(self):
        for field, value in [('native_group_id', '2'), ('private_id', '_rmesh_1_b'),
                             ('original_conductor', 'other'), ('terminal', 9)]:
            b = self.binding()
            b[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                classify(self.endpoint(), [b])
