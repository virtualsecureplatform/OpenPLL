import unittest

from prototype_xyce_diode_translation import DEFINITION, MODEL, WRAPPER, translate


class GeometryControls(unittest.TestCase):
    def test_both_actual_geometries_and_unchanged_connections(self):
        source = ('.subckt cell a b\n'
                  f'X1 a b {MODEL} area=.4347 perim=2.64\n'
                  f'X2 b a {MODEL} area=.6417 perim=3.24\n'
                  'C1 a b -1e-18\n.ends cell\n')
        result, count = translate(source)
        self.assertEqual(count, 2)
        self.assertEqual(result[len(DEFINITION):].replace(WRAPPER, MODEL), source)

    def test_rejects_uncompared_or_ambiguous_parameters(self):
        for geometry in ('area=.5 perim=2.64', 'area=.4347 perim=3.24',
                         'area=.4347 perim=2.64 m=2', 'area=NaN perim=2.64',
                         'area=.4347 area=.4347 perim=2.64'):
            with self.subTest(geometry=geometry), self.assertRaises(ValueError):
                translate(f'X1 a b {MODEL} {geometry}')


if __name__ == '__main__':
    unittest.main()
