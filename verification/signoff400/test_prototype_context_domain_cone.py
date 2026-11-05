import unittest
from inventory_prototype_context_domains import parent_cone


class WholeCellCone(unittest.TestCase):
    def test_parent_cells_are_complete_and_rails_do_not_pull_in_unrelated_logic(self):
        terms={'core':['out','g'],'p0':['out','mid','g'],'p1':['hidden','g'],'up':['mid','ctrl','g'],'digital':['ctrl','g'],'unrelated':['z','g']}
        roles={'core':'oscillator','p0':'parent','p1':'parent','up':'parent','digital':'digital','unrelated':'parent'}
        cells={'core':'c','p0':'buffer','p1':'buffer','up':'upstream','digital':'digital','unrelated':'other'}
        selected,layers,cut,nodes=parent_cone(terms,roles,cells,{'g'})
        self.assertEqual(selected,{'core','p0','p1','up'})
        self.assertEqual(layers,[['p0','p1'],['up']])
        self.assertEqual(cut,{'ctrl':['digital']})
        self.assertNotIn('g',nodes)


if __name__=='__main__':unittest.main()
