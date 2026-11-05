import unittest
from review_prototype_first_stage_ranges import capacitance


class FirstStageCapacitanceRanges(unittest.TestCase):
    def test_scalar_and_range_units(self):
        self.assertEqual(capacitance(' Total capacitance: 0.003\n'),(3,3))
        self.assertEqual(capacitance(' Total capacitance: 0.003-0.005\n'),(3,5))

    def test_ambiguous_reversed_or_missing_rejected(self):
        for text in (' Total capacitance: 0.005-0.003\n','missing',
                     ' Total capacitance: 0.003\n Total capacitance: 0.004\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):capacitance(text)


if __name__=='__main__':unittest.main()
