import unittest
from freeze_parent_routes import freeze_background

class FreezeParentRoutes(unittest.TestCase):
    def test_repeated_repair_preserves_fixed_and_new_routes(self):
        source='NETS 3 ;\n- old ( a A ) + FIXED met2 ( 1 2 ) ( 3 4 ) ;\n- other ( b A ) + ROUTED met3 ( 5 6 ) ( 7 8 ) ;\n- target ( c A ) + ROUTED met4 ( 9 0 ) ( 1 2 ) ;\nEND NETS'
        result,names=freeze_background(source,{'target'})
        self.assertEqual(names,['old','other'])
        self.assertIn('+ FIXED met2 ( 1 2 ) ( 3 4 )',result)
        self.assertIn('+ FIXED met3 ( 5 6 ) ( 7 8 )',result)
        self.assertIn('+ ROUTED met4 ( 9 0 ) ( 1 2 )',result)
        again,names2=freeze_background(result,{'target'})
        self.assertEqual((again,names2),(result,names))
    def test_duplicate_background_rejected(self):
        with self.assertRaises(ValueError):freeze_background('- a + FIXED m1 ;\n- a + ROUTED m1 ;',set())
