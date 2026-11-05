import unittest
from extend_prototype_macro_obstructions import add_obstructions, rectangles
from audit_prototype_macro_interface_reuse import interface

SOURCE = '''MACRO test
  SIZE 10 BY 10 ;
  PIN A
    DIRECTION INPUT ;
    PORT
      LAYER met2 ;
      RECT 0 0 1 1 ;
    END
  END A
  OBS
    LAYER met2 ;
    RECT 2 2 3 3 ;
  END
END test
END LIBRARY
'''


class MacroObstructionTests(unittest.TestCase):
    def test_additions_preserve_interface_and_original_obstructions(self):
        result = add_obstructions(SOURCE, {'met2': [(3000,3000,3100,3200)],
                                           'via': [(4000,4000,4150,4150)]})
        self.assertEqual(interface(result), interface(SOURCE))
        pins, obs = rectangles(result)
        self.assertEqual(pins, rectangles(SOURCE)[0])
        self.assertIn((2000,2000,3000,3000), obs['met2'])
        self.assertIn((3000,3000,3100,3200), obs['met2'])
        self.assertEqual(obs['via'], [(4000,4000,4150,4150)])

    def test_invalid_geometry_or_unknown_layer_rejected(self):
        for additions in ({'met6': [(0,0,1,1)]}, {'met2': [(0,0,0,1)]}):
            with self.assertRaises(ValueError):
                add_obstructions(SOURCE, additions)
        with self.assertRaises(ValueError):
            add_obstructions(SOURCE.replace('  OBS\n',''), {})
