import unittest
from replay_prototype_parent_port_alias_lvs import normalize

TEXT='''.subckt C TRACKING BBPD_RESET_N VDD
R0 TRACKING BBPD_RESET_N 0.000000
Xlogic TRACKING VDD model
.ends C
.subckt T TRACKING VDD
Xc TRACKING reset_wire VDD C
Xd reset_wire VDD other
.ends T
'''

class ParentPortAliasLVS(unittest.TestCase):
    def test_exact_child_short_is_propagated_without_rewriting_child(self):
        normalized,proof=normalize(TEXT,'T','C')
        self.assertIn('R0 TRACKING BBPD_RESET_N 0.000000',normalized)
        self.assertIn('Xc TRACKING TRACKING VDD C',normalized)
        self.assertIn('Xd TRACKING VDD other',normalized)
        self.assertEqual(len(proof['changed_parent_arguments']),2)
        self.assertTrue(proof['child_geometry_and_netlist_unchanged'])

    def test_small_nonzero_resistance_and_two_external_ports_rejected(self):
        with self.assertRaisesRegex(ValueError,'exact-zero-ohm'):normalize(TEXT.replace('0.000000','1e-18'),'T','C')
        with self.assertRaisesRegex(ValueError,'external port identities'):normalize(TEXT.replace('.subckt T TRACKING VDD','.subckt T TRACKING reset_wire VDD'),'T','C')

if __name__=='__main__':unittest.main()
