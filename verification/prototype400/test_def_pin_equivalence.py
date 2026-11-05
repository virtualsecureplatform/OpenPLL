"""PG metadata normalization must preserve the complete physical pin section."""
import unittest
from def_pin_equivalence import pin_sections_equivalent

BASE='''PINS 3 ;
 - VPWR + NET VPWR + DIRECTION INOUT + USE POWER
  + PORT + LAYER met5 ( -5000 -800 ) ( 5000 800 )
  + FIXED ( 500000 50000 ) N ;
 - VGND + NET VGND + DIRECTION INOUT + USE GROUND
  + PORT + LAYER met5 ( -5000 -800 ) ( 5000 800 )
  + FIXED ( 500000 60000 ) N ;
 - CLK + NET CLK + DIRECTION INPUT + USE SIGNAL
  + PORT + LAYER met3 ( -400 -150 ) ( 400 150 )
  + PLACED ( 400 150960 ) N ;
END PINS
'''


class DefPinEquivalence(unittest.TestCase):
    def test_only_pg_special_annotation_can_change(self):
        special=BASE.replace('+ NET VPWR','+ NET VPWR + SPECIAL').replace('+ NET VGND','+ NET VGND + SPECIAL')
        self.assertTrue(pin_sections_equivalent(BASE,special))
        self.assertTrue(pin_sections_equivalent(special,BASE))
        for text in (special.replace('500000 50000','500001 50000'),
                     special.replace('5000 800','5000 801'),special.replace('met5','met4'),
                     special.replace('+ NET CLK','+ NET OTHER'),special.replace('USE POWER','USE SIGNAL'),
                     special.replace('+ NET CLK','+ NET CLK + SPECIAL'),special.replace('+ FIXED','+ PLACED')):
            with self.subTest(text=text):self.assertFalse(pin_sections_equivalent(BASE,text))


if __name__=='__main__':unittest.main()
