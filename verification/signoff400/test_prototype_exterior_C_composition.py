import unittest
from fractions import Fraction as F
from compose_prototype_exterior_C_operator import compose
from project_prototype_fixed_rail_C_v2 import FIXED


class ExteriorComposition(unittest.TestCase):
    def test_signed_compensation_remote_endpoints_and_fixed_supply_projection(self):
        exterior={('port','remote'):F(3),('port','rail'):F(2),('remote','rail'):F(-1,10),('other','remote'):F(1,2)}
        interior={('inside','VGND'):F(4)}
        result=compose(exterior,interior,{'port':'inside'},{'rail'})
        self.assertEqual(result[tuple(sorted(('inside',FIXED)))],6)
        self.assertEqual(result[('__exterior/remote','inside')],3)
        self.assertEqual(result[tuple(sorted(('__exterior/remote',FIXED)))],F(-1,10))
        self.assertIn(('__exterior/other','__exterior/remote'),result)

    def test_signal_rail_overlap_and_namespace_collision_rejected(self):
        with self.assertRaises(ValueError):compose({}, {}, {'a':'x'}, {'a'})
        with self.assertRaises(ValueError):compose({}, {('__exterior/x','x'):F(1)}, {}, set())


if __name__=='__main__':unittest.main()
