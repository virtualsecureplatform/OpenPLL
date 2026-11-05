import unittest
from prototype_electrical_branch_eco_v11 import actions_for_plan


class TimingBranchEcoTests(unittest.TestCase):
    def plan(self):
        return dict(targets=[dict(capture_cell='state', capture_master='sky130_fd_sc_hs__dfrtp_1',
                                 replacement_master='sky130_fd_sc_hs__dfrtp_2')], branches=[], source_buffers=[],
                    short_data_targets=[dict(capture_cell='state', capture_master='sky130_fd_sc_hs__dfrtp_1',
                                             capture_pin='D', buffers=2)])

    def test_resize_precedes_hold_and_post_resize_master_checked(self):
        text = actions_for_plan(self.plan())
        self.assertLess(text.index('replace_cell'), text.index('set sink'))
        self.assertIn('ne {sky130_fd_sc_hs__dfrtp_2}', text[text.index('set sink'):])
        self.assertEqual(text.count('odb::dbInst_create'), 2)
        self.assertIn('prototype_wire_timing_hold_0_1', text)
        self.assertNotIn('prototype_observed_load_hold_', text)

    def test_clock_or_unbounded_delay_change_rejected(self):
        for key, value in [('capture_pin', 'CLK'), ('buffers', 3)]:
            plan = self.plan(); plan['short_data_targets'][0][key] = value
            with self.assertRaises(ValueError): actions_for_plan(plan)

    def test_native_set_flop_D_pin_is_eligible(self):
        plan = self.plan(); plan['targets'] = []
        plan['short_data_targets'][0]['capture_master'] = 'sky130_fd_sc_hs__dfstp_2'
        self.assertIn('ne {sky130_fd_sc_hs__dfstp_2}', actions_for_plan(plan))

    def test_same_family_requirement_preserved(self):
        plan = self.plan(); plan['targets'][0]['replacement_master'] = 'sky130_fd_sc_hs__dfstp_2'
        with self.assertRaises(ValueError): actions_for_plan(plan)


if __name__ == '__main__': unittest.main()
