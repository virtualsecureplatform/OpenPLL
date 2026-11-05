import unittest
from prototype_measured_path_eco import actions_for_plan


class MeasuredPathEcoTests(unittest.TestCase):
    def test_two_inputs_on_same_logic_cell_can_be_repaired_independently(self):
        targets = [dict(capture_cell='logic', capture_master='sky130_fd_sc_hs__nor2_1',
                        capture_pin=pin, buffers=1) for pin in ('A', 'B')]
        text = actions_for_plan(targets)
        self.assertEqual(text.count('odb::dbInst_create'), 2)
        self.assertIn('findITerm A', text)
        self.assertIn('findITerm B', text)
        self.assertNotIn('findITerm CLK', text)

    def test_different_logic_function_cannot_be_substituted(self):
        with self.assertRaises(ValueError):
            actions_for_plan([dict(action='resize', capture_cell='logic',
                capture_master='sky130_fd_sc_hs__nor2_1', replacement_master='sky130_fd_sc_hs__nand2_2')])

    def test_clock_pin_is_not_eligible_for_data_buffering(self):
        with self.assertRaises(ValueError):
            actions_for_plan([dict(capture_cell='state', capture_master='sky130_fd_sc_hs__dfrtp_1',
                                  capture_pin='CLK', buffers=1)])


if __name__ == '__main__':
    unittest.main()
