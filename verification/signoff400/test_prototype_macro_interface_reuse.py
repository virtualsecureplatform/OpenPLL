import unittest
from audit_prototype_macro_interface_reuse import interface

A='''MACRO M
ORIGIN 0 0 ;
SIZE 1.00 BY 2 ;
PIN A
 DIRECTION INPUT ;
 PORT
 LAYER met3 ;
 RECT 0.010 0 0.10 0.20 ;
 END
END A
END M
'''

class MacroInterfaceReuseTests(unittest.TestCase):
    def test_numeric_spelling_does_not_change_pin_geometry(self):
        self.assertEqual(interface(A),interface(A.replace('0.010','1e-2').replace('1.00','1')))

    def test_small_pin_motion_is_not_ignored(self):
        self.assertNotEqual(interface(A)['pins'],interface(A.replace('0.010','0.011'))['pins'])
        with self.assertRaises(ValueError):interface(A.replace('END A','END B'))

if __name__=='__main__':unittest.main()
