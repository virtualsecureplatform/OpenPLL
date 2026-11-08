import unittest
from plan_keeper_conditional_replay import plan,bind_variables

class ReplayBindings(unittest.TestCase):
    def bindings(self):return dict(externally_driven_ports={'hier.x':'P0'},observation_only_ports={'PLLOUT':'P1'})
    def test_hierarchical_and_top_level_nodes(self):
        records=plan(self.bindings(),{'hier.x':'__geometry_node_65','PLLOUT':'PLLOUT'},{'PLLOUT'})
        bound=bind_variables(records,['TIME','v(xdut:__geometry_node_65)','V(PLLOUT)'])
        self.assertEqual(bound['hier.x']['RAW_index'],1)
        self.assertEqual(bound['PLLOUT']['role'],'observation_only')
    def test_missing_physical_node_rejected(self):
        with self.assertRaises(ValueError):plan(self.bindings(),{'PLLOUT':'PLLOUT'},{'PLLOUT'})
    def test_missing_RAW_variable_rejected(self):
        records=plan(self.bindings(),{'hier.x':'n','PLLOUT':'PLLOUT'},{'PLLOUT'})
        with self.assertRaises(ValueError):bind_variables(records,['TIME','V(PLLOUT)'])
    def test_forced_output_rejected(self):
        b=self.bindings();b['externally_driven_ports']['PLLOUT']='P1'
        with self.assertRaises(ValueError):plan(b,{},set())
    def test_duplicate_case_folded_variables_rejected(self):
        with self.assertRaises(ValueError):bind_variables({},['V(A)','v(a)'])

if __name__=='__main__':unittest.main()
