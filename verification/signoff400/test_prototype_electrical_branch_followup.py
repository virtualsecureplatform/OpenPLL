import unittest
from prototype_electrical_branch_eco_v3 import actions_for_plan

class ElectricalFollowupNames(unittest.TestCase):
    def test_preserves_existing_sink_and_creates_fresh_namespace(self):
        plan=dict(targets=[],branches=[dict(driver=dict(cell='old_driver',pin='Y',master='xnor'),sinks=[dict(cell='prototype_electrical_branch_2_0',pin='A',master='sky130_fd_sc_hs__clkbuf_2')],max_sinks_per_buffer=8,buffer_master='sky130_fd_sc_hs__clkbuf_2')])
        text=actions_for_plan(plan)
        self.assertIn('findInst {prototype_electrical_branch_2_0}',text)
        self.assertIn('set prefix prototype_electrical_followup_0_$start',text)
        self.assertIn('fresh electrical branch names required',text)
    def test_rejects_unsupported_residual_hold_pin(self):
        with self.assertRaises(ValueError):actions_for_plan(dict(targets=[],branches=[],short_data_targets=[dict(capture_pin='CLK',capture_master='sky130_fd_sc_hs__dfrtp_1',buffers=1)]))

if __name__=='__main__':unittest.main()
