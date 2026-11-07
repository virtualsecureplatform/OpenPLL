import unittest
from collections import defaultdict
from fractions import Fraction as F
from compare_keeper_primary_C import stamp,groups

class PrimaryRestriction(unittest.TestCase):
    def test_known_two_port_energy(self):
        matrix=defaultdict(F);mapping={'a':('A',),'b':('B',)}
        for a,b,c in [('a','0',2),('a','b',3),('b','0',4)]:stamp(matrix,a,b,F(c),mapping)
        self.assertEqual(matrix,{(('A',),('A',)):5,(('B',),('B',)):7,(('A',),('B',)):-3})
        self.assertEqual(matrix[(('A',),('A',))]+4*matrix[(('B',),('B',))]+4*matrix[(('A',),('B',))],21)
    def test_internal_clamped_node_contributes_diagonal(self):
        m=defaultdict(F);stamp(m,'a','private',F(7),{'a':('A',)})
        self.assertEqual(m,{(('A',),('A',)):7})
    def test_zero_R_alias_partition_and_supplies(self):
        canonical=lambda n:{'ALIAS':'A','VPB':'VPWR'}.get(n,n)
        self.assertEqual(groups(['A','ALIAS','VPWR','VPB'],canonical),{'A':('A','ALIAS')})
        m=defaultdict(F);stamp(m,'same','same',F(7),{'same':('A','ALIAS')});self.assertFalse(m)
if __name__=='__main__':unittest.main()
