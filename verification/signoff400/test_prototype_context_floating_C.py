import unittest
from fractions import Fraction as F
from inventory_prototype_context_floating_C import inventory


class ContextFloating(unittest.TestCase):
    def test_active_terminals_and_named_ports_cannot_be_eliminated(self):
        p={('active','f1'):F(1),('f1','f2'):F(2),('f2','port'):F(1),('g','stray'):F(1)}
        groups,stats=inventory(p,{'active','port','g','noC'})
        self.assertEqual(stats['capacitor_only_nodes'],3)
        self.assertEqual(stats['active_terminal_nodes_without_geometric_C'],1)
        self.assertEqual(groups[0]['nodes'],['f1','f2'])
        self.assertEqual(groups[0]['boundaries'],['active','port'])

    def test_signed_floating_incidence_is_reported_without_modification(self):
        p={('active','f'):F(-1),('f','g'):F(2)}
        groups,_=inventory(p,{'active','g'})
        self.assertEqual(groups[0]['negative_incident_pairs'],1)
        self.assertEqual(p[('active','f')],-1)


if __name__=='__main__':unittest.main()
