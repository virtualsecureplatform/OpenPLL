import unittest
from presize_prototype_electrical_plan import changes_for_driver,electrical_driver,resize_tcl


class PresizingTests(unittest.TestCase):
    def test_sizes_progress_from_original_master_and_protected_state_stays_fixed(self):
        cells={'gate':{'type':'lib__nor2_1'},'first':{'type':'lib__nor2_1'}}
        available={'lib__nor2_1','lib__nor2_2','lib__nor2_4'};targets={};buffers={}
        self.assertTrue(changes_for_driver('gate','Y',cells,targets,buffers,{'first'},available))
        self.assertTrue(changes_for_driver('gate','Y',cells,targets,buffers,{'first'},available))
        self.assertEqual(targets['gate']['capture_master'],'lib__nor2_1')
        self.assertEqual(targets['gate']['replacement_master'],'lib__nor2_4')
        self.assertFalse(changes_for_driver('first','Y',cells,targets,buffers,{'first'},available))
        self.assertNotIn('first',targets)

    def test_pending_buffer_checks_post_resize_master_and_is_not_duplicated(self):
        cells={'gate':{'type':'lib__nor2_1'}};targets={'gate':dict(replacement_master='lib__nor2_4')};buffers={}
        available={'lib__nor2_4','sky130_fd_sc_hs__clkbuf_8'}
        self.assertTrue(changes_for_driver('gate','Y',cells,targets,buffers,set(),available))
        self.assertEqual(buffers['gate']['driver']['master'],'lib__nor2_4')
        self.assertFalse(changes_for_driver('gate','Y',cells,targets,buffers,set(),available))

    def test_output_port_and_receiver_pin_resolve_to_same_unique_driver(self):
        module={'ports':{'OUT':{'bits':[2,3]}}};cells={'sink':{'connections':{'A':[3]}}};drivers={3:[('driver','Y')]}
        self.assertEqual(electrical_driver('OUT[1]',module,cells,drivers),('driver','Y'))
        self.assertEqual(electrical_driver('sink/A',module,cells,drivers),('driver','Y'))
        with self.assertRaises(ValueError):electrical_driver('OUT[0]',module,cells,drivers)

    def test_function_or_unsafe_name_change_cannot_be_rendered(self):
        for name,new in [('gate','lib__nand2_2'),('bad}name','lib__nor2_2')]:
            with self.assertRaises(ValueError):resize_tcl({name:dict(capture_master='lib__nor2_1',replacement_master=new)})


if __name__=='__main__':unittest.main()
