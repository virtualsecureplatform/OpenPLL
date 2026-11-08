import unittest
from fractions import Fraction
from audit_keeper_prescribed_boundary_roles import inventory


class PrescribedRoles(unittest.TestCase):
    def interface(self):
        return dict(externally_driven_ports=['gate','ext','VPWR'],
                    observation_only_ports=['PLLOUT'],interior_nodes=['n','bulk'])

    def test_primitive_and_capacitive_dependencies_remain_distinct(self):
        text='''X1 PLLOUT gate n bulk sky130_fd_pr__nfet_01v8 w=1 l=1
C1 ext n 2f
C2 ext PLLOUT 3f
C3 ext gate 4f
C4 VPWR n 5f
'''
        rows={r['node']:r for r in inventory(text,self.interface())}
        self.assertEqual(rows['gate']['terminal_roles'],['MOS_gate'])
        self.assertEqual(rows['ext']['kind'],'capacitive_only')
        self.assertEqual(Fraction(rows['ext']['C_to_unknowns_F_exact']),Fraction(5,10**15))
        self.assertEqual(rows['VPWR']['kind'],'rail')
        self.assertEqual(rows['ext']['support']['capacitors_to_prescribed_or_ground'],1)

    def test_diffusion_connection_is_not_mislabeled_capacitive(self):
        text='X1 ext gate n bulk sky130_fd_pr__nfet_01v8 w=1 l=1\n'
        rows={r['node']:r for r in inventory(text,self.interface())}
        self.assertEqual(rows['ext']['terminal_roles'],['MOS_diffusion'])

    def test_bad_partition_negative_C_and_duplicate_cards_rejected(self):
        for text in ['C1 ext n -1f\n','C1 ext missing 1f\n','C1 ext n 1f\nC1 ext n 1f\n']:
            with self.assertRaises(ValueError):inventory(text,self.interface())


if __name__=='__main__':
    unittest.main()
