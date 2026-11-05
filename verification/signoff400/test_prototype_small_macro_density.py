import unittest
from review_prototype_small_macro_density import LAYERS, measure


class SmallMacroDensityTest(unittest.TestCase):
    def fixture(self):
        text = 'XTILES: 2\nYTILES: 1\nXFRAC: 0.5\nYFRAC: 1\n'
        for x, value in ((0, '0.6'), (1, '0.3')):
            text += f'Density results for tile x={x} y=0\n'
            text += ''.join(f'{layer}: {value}\n' for layer in LAYERS)
        return text+'Ended: fixture\nMagic exited with status 0\nLayout is < 700um x 700um; cannot run density checks.\n'

    def test_clipped_edge_weighting_and_nonpass(self):
        result = measure(self.fixture(), [0, 0, 105000, 70000])
        self.assertEqual(result['results']['MET5']['global_density'], '0.5')
        self.assertEqual(result['failed_global_checks'], 0)
        failed = measure(self.fixture().replace('MET5: 0.6', 'MET5: 0.1'), [0, 0, 105000, 70000])
        self.assertFalse(failed['results']['MET5']['within_limits'])

    def test_incomplete_duplicate_or_wrong_extent_rejected(self):
        original = self.fixture()
        for damaged, die in ((original.replace('MET5: 0.3\n', ''), [0, 0, 105000, 70000]),
                             (original.replace('x=1 y=0', 'x=0 y=0'), [0, 0, 105000, 70000]),
                             (original, [0, 0, 140000, 70000]),
                             (original.replace('Magic exited with status 0', ''), [0, 0, 105000, 70000])):
            with self.subTest(damaged=damaged, die=die), self.assertRaises(ValueError):
                measure(damaged, die)


if __name__ == '__main__':
    unittest.main()
