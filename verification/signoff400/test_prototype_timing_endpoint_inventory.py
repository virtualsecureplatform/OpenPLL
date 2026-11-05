import unittest
from inventory_prototype_timing_endpoints import paths


class EndpointInventoryTests(unittest.TestCase):
    def test_retains_both_checks_and_signed_slack(self):
        text = ('Startpoint: source (flip-flop)\nEndpoint: sink (flip-flop)\n'
                'Path Type: min\n -0.090077 slack (VIOLATED)\n'
                'Startpoint: source (flip-flop)\nEndpoint: sink (flip-flop)\n'
                'Path Type: max\n 1.464077 slack (MET)\n')
        self.assertEqual([(p['kind'], p['slack_ns']) for p in paths(text)],
                         [('min', -0.090077), ('max', 1.464077)])

    def test_partial_native_path_is_rejected(self):
        with self.assertRaises(ValueError):
            paths('Startpoint: source\nEndpoint: sink\nPath Type: min\n')


if __name__ == '__main__':
    unittest.main()
