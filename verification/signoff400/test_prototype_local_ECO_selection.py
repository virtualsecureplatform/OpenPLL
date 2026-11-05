import unittest
from select_prototype_local_ECO_routes import change_windows,overlaps,tcl_literal,route_records


class LocalEcoSelectionTests(unittest.TestCase):
    def test_same_position_master_resize_is_still_a_physical_change(self):
        old={'gate':dict(master='nand2_1',bbox=[10,20,30,40],orient='R0')}
        new={'gate':dict(master='nand2_2',bbox=[10,20,30,40],orient='R0')}
        changed,windows=change_windows(old,new,2)
        self.assertEqual(changed,['gate']);self.assertIn((8,18,32,42),windows)

    def test_spacer_rebuild_is_ignored_but_removed_logic_is_rejected(self):
        old={'filler':dict(master='sky130_fd_sc_hs__fill_8',bbox=[0,0,8,3],orient='R0')}
        self.assertEqual(change_windows(old,{},2),([],[]))
        old['logic']=dict(master='nand2_1',bbox=[0,0,1,3],orient='R0')
        with self.assertRaises(ValueError):change_windows(old,{},2)

    def test_crossing_segments_and_exact_escaped_names_are_preserved(self):
        self.assertTrue(overlaps((0,5,20,5),(9,4,11,6)))
        self.assertFalse(overlaps((0,5,8,5),(9,4,11,6)))
        self.assertEqual(tcl_literal(r'$abc$net\[0\]'),r'{$abc$net\[0\]}')
        with self.assertRaises(ValueError):tcl_literal('unsafe}name')

    def test_indented_DEF_routes_are_compared_independent_of_whitespace(self):
        first='NETS 2 ;\n  - n1 ( g Y ) + ROUTED met1 ( 0 0 ) ( 1 0 ) ;\n  - n2 ( g A ) ;\nEND NETS\n'
        second=first.replace('  -','-').replace('met1 (','met1\n (')
        self.assertEqual(route_records(first),route_records(second))
        self.assertEqual(set(route_records(first)),{'n1'})
        with self.assertRaises(ValueError):route_records('NETS 0 ;\nEND NETS\n')


if __name__=='__main__':unittest.main()
