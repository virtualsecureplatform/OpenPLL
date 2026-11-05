import unittest
from prototype_interstage_hold_repair import actions_for_plan


class InterstageRepairTests(unittest.TestCase):
    def target(self):
        return dict(capture_cell='$auto$ff:123', capture_master='sky130_fd_sc_hs__dfrtp_1', buffers=3)

    def test_buffer_chain_changes_only_capture_data(self):
        text = actions_for_plan([self.target()])
        self.assertEqual(text.count('odb::dbInst_create'), 3)
        self.assertEqual(text.count('$data connect $upstream'), 1)
        self.assertNotIn('findITerm CLK', text)
        self.assertNotIn('findITerm RESET_B', text)
        self.assertIn('sky130_fd_sc_hs__clkbuf_2', text)

    def test_duplicate_sink_and_unbounded_or_injected_targets_rejected(self):
        target = self.target()
        with self.assertRaises(ValueError):
            actions_for_plan([target, target])
        for key, value in [('buffers', 100), ('capture_cell', 'sink}\nexit')]:
            with self.assertRaises(ValueError):
                actions_for_plan([{**target, key: value}])


if __name__ == '__main__':
    unittest.main()
