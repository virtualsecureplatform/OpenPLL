import unittest
from select_prototype_fixed_logic_incident_routes import fixed_changes


class FixedIncidentRoutes(unittest.TestCase):
    def test_only_insertions_and_spacer_replacements_are_accepted(self):
        gate=dict(master='nand2_1',bbox=[0,0,10,3],orient='R0')
        before={'gate':gate,'filler':dict(master='sky130_fd_sc_hs__fill_8',bbox=[10,0,18,3],orient='R0')}
        after={'gate':dict(gate),'buffer':dict(master='clkbuf_8',bbox=[10,0,15,3],orient='R0')}
        self.assertEqual(fixed_changes(before,after),['buffer'])

    def test_existing_master_position_or_orientation_changes_are_rejected(self):
        old={'gate':dict(master='nand2_1',bbox=[0,0,10,3],orient='R0')}
        for change in (dict(master='nand2_2'),dict(bbox=[1,0,11,3]),dict(orient='MX')):
            new={'gate':dict(old['gate'],**change)}
            with self.assertRaises(ValueError):fixed_changes(old,new)
        with self.assertRaises(ValueError):fixed_changes(old,{})
        with self.assertRaises(ValueError):fixed_changes(old,old)


if __name__=='__main__':unittest.main()
