import unittest

from prototype_xyce_resistor_translation import DEFINITION, WRAPPER, translate


class TranslationControls(unittest.TestCase):
    def test_only_model_call_changes(self):
        source = ('* fixture\n.subckt cell p n\n'
                  'Xr p n sky130_fd_pr__res_generic_po l=0.045 w=0.51\n'
                  'C1 p n -1e-18\nRwire p n 0.15\n.ends cell\n')
        result, count = translate(source)
        recovered = result[len(DEFINITION):].replace(WRAPPER, 'sky130_fd_pr__res_generic_po')
        self.assertEqual(recovered, source)
        self.assertEqual(count, 1)

    def test_rejects_unvalidated_geometry_and_parameters(self):
        for tail in ('l=0 w=1', 'l=NaN w=1', 'l={v} w=1', 'l=1u w=1',
                     'l=1 w=1 m=2', 'l=1 l=2 w=1', 'l=1'):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                translate('Xr p n sky130_fd_pr__res_generic_po ' + tail)

    def test_rejects_namespace_reuse(self):
        with self.assertRaises(ValueError):
            translate(DEFINITION)


if __name__ == '__main__':
    unittest.main()
