import unittest
from fractions import Fraction as F
from check_prototype_cell_geometry_conversion_v2 import extracted_features,spice_features


class CellGeometryControls(unittest.TestCase):
    def test_mos_grid_converts_to_native_micrometers(self):
        ext='device msubckt sky130_fd_pr__nfet_01v8 0 0 1 1 l=30 w=84\n'
        spice='.subckt cell D G S B\nX0 D G S B sky130_fd_pr__nfet_01v8 l=0.15 w=0.42\n.ends\n'
        self.assertEqual(extracted_features(ext,F(1,200)),spice_features(spice))
        self.assertNotEqual(extracted_features(ext,F(1,100)),spice_features(spice))

    def test_poly_resistor_and_scaled_diode_conventions(self):
        ext='device rsubckt sky130_fd_pr__res_generic_po 0 0 1 1 l=9 w=102\ndevice msubckt sky130_fd_pr__diode_pw2nd_05v5 0 0 1 1 a=25668 p=648\n'
        spice='.subckt cell A B\nXr A B sky130_fd_pr__res_generic_po l=0.045 w=0.51\nXd A B sky130_fd_pr__diode_pw2nd_05v5 area=6.417e11 perim=3.24e6\n.ends\n'
        self.assertEqual(extracted_features(ext,F(1,200)),spice_features(spice))

    def test_unreviewed_device_record_and_implicit_multiplicity_rejected(self):
        with self.assertRaises(ValueError):extracted_features('device unknown model',F(1,200))
        with self.assertRaises(ValueError):spice_features('.subckt cell a b\nX0 a b sky130_fd_pr__res_generic_po l=1 w=1 m=2\n.ends\n')


if __name__=='__main__':unittest.main()
