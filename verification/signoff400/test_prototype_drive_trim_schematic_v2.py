from collections import Counter
import unittest
from prepare_prototype_drive_trim_schematic_v2 import build
from test_prototype_drive_trim_schematic import models


class ThreeStageDriveTrimTests(unittest.TestCase):
    def cells(self):
        result = models()
        old = result.pop('sky130_fd_sc_hd__einvn_0')
        result['sky130_fd_sc_hd__einvn_1'] = old.replace('einvn_0', 'einvn_1')
        return result

    def test_each_fine_control_loads_both_controlled_stages_once(self):
        text = build(self.cells(), 510, 8, 2)
        rows = [line.split() for line in text.splitlines() if line.startswith('Xfine_')]
        self.assertEqual(Counter((r[1], r[2]) for r in rows),
                         Counter({(f'DCO_THERM[{i}]', f'ring{stage}'): 1
                                  for i in range(255) for stage in (1, 2)}))
        self.assertEqual(sum(l.startswith('Xbaseline_') for l in text.splitlines()), 16)
        self.assertEqual(sum(l.startswith('Xboost_') for l in text.splitlines()), 94)
        self.assertIn('Xreset_gate ring2 RESET_N ring0 ', text)

    def test_even_total_inversion_count_and_zero_baseline_are_rejected(self):
        for baseline, stages in [(8, 3), (0, 2), (33, 2)]:
            with self.assertRaises(ValueError):
                build(self.cells(), 510, baseline, stages)


if __name__ == '__main__':
    unittest.main()
