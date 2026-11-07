import unittest
from build_prototype_full_C_wire_R_v11 import build
from test_coalesced_child_wire_R import TEXT,spef

class FiniteChildWireJoin(unittest.TestCase):
    def test_existing_wire_path_connects_coalesced_parent_networks(self):
        for attachment in ['driver','farthest']:
            _,m,_=build(TEXT.replace('Rshort A B 0','Rshort A B 17'),'Top',spef(),{'cell':'cell'},attachment)
            join=m['coalesced_root_wire_networks'][0]
            self.assertFalse(join['child_zero_R_join_verified'])
            self.assertTrue(join['child_resistor_path_join_verified'])
            self.assertTrue(m['existing_resistor_topology_recovered'])
    def test_unrelated_resistor_is_not_a_join(self):
        with self.assertRaisesRegex(ValueError,'lacks actual child'):
            build(TEXT.replace('Rshort A B 0','Rother Z VGND 17'),'Top',spef(),{'cell':'cell'})

if __name__=='__main__':unittest.main()
