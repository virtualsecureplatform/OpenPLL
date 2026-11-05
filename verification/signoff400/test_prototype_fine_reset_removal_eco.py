import unittest
from prototype_fine_reset_removal_eco import actions_for_plan

class FineResetBranches(unittest.TestCase):
    def fixture(self):
        return dict(targets=[],branches=[],reset_branches=[dict(capture_cells=[f'receiver_{i}'],capture_master='sky130_fd_sc_hs__dfstp_1',capture_pin='SET_B',buffers=8,last_buffer_master='sky130_fd_sc_hs__clkbuf_4') for i in range(5)])
    def test_only_set_pins_are_rewired_and_shared_net_checked(self):
        text=actions_for_plan(self.fixture())
        self.assertEqual(text.count('odb::dbInst_create'),40)
        self.assertEqual(text.count('findMaster sky130_fd_sc_hs__clkbuf_4'),5)
        self.assertNotIn('findITerm D]',text)
        self.assertIn('reset branch no longer shares one leaf net',text)
    def test_rejects_other_pin_and_unbounded_delay(self):
        for key,value in [('capture_pin','D'),('buffers',9)]:
            plan=self.fixture();plan['reset_branches'][0][key]=value
            with self.assertRaises(ValueError):actions_for_plan(plan)

if __name__=='__main__':unittest.main()
