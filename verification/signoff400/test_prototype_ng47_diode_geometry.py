import unittest
from convert_prototype_ng47_diode_geometry import convert,check

SOURCE='''.subckt diode_cell N P
X0 N P sky130_fd_pr__diode_pw2nd_05v5 area=4.347e11 perim=2.64e6
.ends diode_cell
.subckt IntegerPLL_BBPD OUT IN VGND VPWR VNB VPB
Xdiode1 VGND IN diode_cell
Xdiode2 VGND OUT diode_cell
Xactive OUT IN VGND VNB sky130_fd_pr__nfet_01v8 w=.65 l=.15 ad=.01
Cnegative IN OUT -0.01f
.ends IntegerPLL_BBPD
'''


class Ng47DiodeGeometryIntegrity(unittest.TestCase):
    def test_shared_leaf_is_converted_once_and_expanded_geometry_checked(self):
        text,changes=convert(SOURCE);proof=check(SOURCE,text,'IntegerPLL_BBPD')
        self.assertEqual(len(changes),1)
        self.assertEqual(proof['expanded_diodes'],2)
        self.assertEqual(proof['expanded_primitive_instances'],3)
        self.assertIn('area=0.4347 perim=2.64',text)
        self.assertIn('Cnegative IN OUT -0.01f',text)
        self.assertIn('w=.65 l=.15 ad=.01',text)
        self.assertTrue(proof['exact_expanded_conversion_reparse_pass'])

    def test_unknown_or_already_converted_geometry_is_rejected(self):
        converted,_=convert(SOURCE)
        for text in (converted,SOURCE.replace('area=4.347e11','area=1e11'),SOURCE.replace('perim=2.64e6','pj=2.64e6')):
            with self.assertRaises(ValueError):convert(text)
        with self.assertRaises(ValueError):check(SOURCE,converted.replace('w=.65','w=.66'),'IntegerPLL_BBPD')


if __name__=='__main__':unittest.main()
