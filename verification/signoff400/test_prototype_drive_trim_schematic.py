from collections import Counter
import unittest
from prepare_prototype_drive_trim_schematic import build


def models():
    return {f'sky130_fd_sc_hd__{name}': f'.subckt sky130_fd_sc_hd__{name} {pins}\n.ends\n'
            for name, pins in [('nand2_8', 'A B Y VGND VPWR VPB VNB'),
                               ('einvp_1', 'TE A Z VPWR VGND VPB VNB'),
                               ('einvn_0', 'TE_B A Z VGND VPWR VPB VNB'),
                               ('buf_8', 'A X VGND VPWR VPB VNB')]}


class DriveTrimSchematicTests(unittest.TestCase):
    def test_all_fine_controls_preserved_and_distributed_over_six_stages(self):
        text = build(models(), 1020)
        rows = [line.split() for line in text.splitlines() if line.startswith('Xfine_')]
        self.assertEqual(Counter(row[1] for row in rows),
                         Counter({f'DCO_THERM[{i}]': 4 for i in range(255)}))
        self.assertEqual(Counter(row[2] for row in rows),
                         Counter({f'ring{i}': 170 for i in range(1, 7)}))
        self.assertEqual(sum(line.startswith('Xbaseline_') for line in text.splitlines()), 6)
        self.assertEqual(sum(line.startswith('Xboost_') for line in text.splitlines()), 6*47)

    def test_fractional_fine_bank_is_rejected(self):
        with self.assertRaises(ValueError):
            build(models(), 1021)

    def test_unknown_functional_pin_cannot_be_left_floating(self):
        cells = models()
        cells['sky130_fd_sc_hd__nand2_8'] = '.subckt sky130_fd_sc_hd__nand2_8 A B Y UNKNOWN\n.ends\n'
        with self.assertRaises(ValueError):
            build(cells, 255)


if __name__ == '__main__':
    unittest.main()
