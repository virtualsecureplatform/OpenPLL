import unittest
from prototype_electrical_branch_eco import actions_for_plan

class ElectricalBranchECO(unittest.TestCase):
    def test_same_family_resize_is_bound_to_old_master(self):
        text=actions_for_plan(dict(targets=[dict(capture_cell='logic',capture_master='sky130_fd_sc_hs__nor2_1',replacement_master='sky130_fd_sc_hs__nor2_4')],branches=[]))
        self.assertIn('ne {sky130_fd_sc_hs__nor2_1}',text)
        self.assertIn('replace_cell {logic} sky130_fd_sc_hs__nor2_4',text)
        with self.assertRaises(ValueError):
            actions_for_plan(dict(targets=[dict(capture_cell='logic',capture_master='sky130_fd_sc_hs__nor2_1',replacement_master='sky130_fd_sc_hs__nand2_4')],branches=[]))
    def test_branch_checks_connectivity_and_groups_eight(self):
        branch=dict(driver=dict(cell='source',pin='Q',master='ff'),sinks=[dict(cell='sink',pin='D',master='ff')],max_sinks_per_buffer=8,buffer_master='sky130_fd_sc_hs__clkbuf_2')
        text=actions_for_plan(dict(targets=[],branches=[branch]))
        self.assertIn('if {[$term getNet] ne $upstream}',text)
        self.assertIn('incr start 8',text)
        self.assertIn('foreach item $group {[lindex $item 3] connect $local}',text)
        branch['buffer_master']='uncharacterized'
        with self.assertRaises(ValueError):actions_for_plan(dict(targets=[],branches=[branch]))

if __name__=='__main__':unittest.main()
