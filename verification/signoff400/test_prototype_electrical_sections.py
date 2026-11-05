import unittest
from inventory_prototype_electrical_limits_v2 import electrical_rows


class ElectricalSections(unittest.TestCase):
    def test_units_stay_with_their_sections(self):
        text=('max slew\n\nPin Limit Slew Slack\n-------\n'
              'driver/Y 1.000000 1.200000 -0.200000 (VIOLATED)\n\n'
              'max capacitance\n\nPin Limit Cap Slack\n-------\n'
              'driver/Y 0.050000 0.080000 -0.030000 (VIOLATED)\n\n')
        rows=electrical_rows(text)
        self.assertEqual([(r[0],r[1]) for r in rows],[('max_slew','ns'),('max_capacitance','pF')])
        self.assertEqual(electrical_rows('no electrical violations\n'),[])

    def test_unknown_row_and_duplicate_section_rejected(self):
        block='max slew\n\nPin Limit Slew Slack\n-------\n'
        for text in (block+'unrecognized row\n\n',block+'\n'+block):
            with self.subTest(text=text),self.assertRaises(ValueError):electrical_rows(text)


if __name__=='__main__':unittest.main()
