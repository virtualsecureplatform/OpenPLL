import unittest
from prototype_local_guide_regions import parse_guides,dump_guides,snap_box,replace_local_guides


class LocalGuideRegions(unittest.TestCase):
    def test_replacement_preserves_other_guide_geometry_and_escaped_names(self):
        text='local\n(\n0 0 10 10 met1\n)\n\\bus[0]\n(\n20 0 30 10 met3\n)\n'
        old=parse_guides(text);new=replace_local_guides(old,{'local':[(0,0,10,20,'met3')]})
        self.assertEqual(new[r'\bus[0]'],old[r'\bus[0]'])
        self.assertEqual(parse_guides(dump_guides(new)),new)
        with self.assertRaises(ValueError):replace_local_guides(old,{'missing':[(0,0,10,10,'met1')]})

    def test_regions_expand_to_grid_and_clip_to_valid_bounds(self):
        self.assertEqual(snap_box((51,81,59,99),3,(0,0),(10,10),(0,0,100,100)),(40,70,70,100))
        with self.assertRaises(ValueError):parse_guides('net\n(\n0 0 0 10 met1\n)\n')
        with self.assertRaises(ValueError):parse_guides('net\n(\n0 0 10 10 met1\n')


if __name__=='__main__':unittest.main()
