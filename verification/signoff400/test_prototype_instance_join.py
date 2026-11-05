import unittest
from fractions import Fraction as F
from join_prototype_physical_instances import dimensions, join


class InstanceJoinControls(unittest.TestCase):
    def test_grid_requires_both_length_and_width(self):
        ext = 'device msubckt nfet 0 0 1 1 l=30 w=130\n'
        spice = '.subckt cell A Z\nX0 Z A Z A nfet l=0.15 w=0.65\n.ends\n'
        self.assertEqual(dimensions(ext, spice, 'cell'), (F(1, 200), 1))
        with self.assertRaises(ValueError):
            dimensions(ext, spice.replace('0.65', '0.66'), 'cell')

    def test_unique_geometry_join_and_complete_cell_coverage(self):
        placements = 'UNITS\t1000\nINST\trtl\tsky130_fd_sc_hd__cell\tMY\t100\t200\t20\t30\n'
        ext = 'use sky130_fd_sc_hd__cell physical -1 0 20 0 1 40\n'
        mapping, scale = join(placements, ext, F(1, 200))
        self.assertEqual(scale, 5)
        self.assertEqual(mapping[0]['extracted_instance'], 'physical')
        for bad in (ext.replace('20', '21'), ext + ext.replace('physical', 'duplicate'),
                    ext + 'use sky130_fd_sc_hd__cell extra 1 0 0 0 1 0\n'):
            with self.assertRaises(ValueError):
                join(placements, bad, F(1, 200))


if __name__ == '__main__':
    unittest.main()
