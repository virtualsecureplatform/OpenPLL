import unittest
from plan_selected_detector_passive_cut import passive_cut

class DetectorPassiveCutTests(unittest.TestCase):
    def test_floating_capacitive_chain_is_preserved_to_active_boundary(self):
        terms={'inside':['a','VGND'],'outside':['z','VGND'],'load':['a','VGND']}
        cards=[('C0','a','float1'),('C1','float1','float2'),('R0','float2','z'),
               ('C2','z','VGND'),('C3','other','VGND')]
        private,boundary,retained,omitted=passive_cut(terms,cards,{'inside'})
        self.assertEqual(private,{'a','float1','float2'})
        self.assertEqual(boundary,{'z'})
        self.assertEqual(retained,{0,1,2})
        self.assertEqual(omitted,{'load':['a']})
    def test_prescribed_input_stops_expansion_but_output_stays_unknown(self):
        p,b,c,o=passive_cut({'inside':['output','reset'],'driver':['reset','driver_internal']},
                           [('R0','output','input'),('C0','reset','driver_internal')],
                           {'inside'},{'input','reset'})
        self.assertEqual(p,{'output'})
        self.assertEqual(b,{'input','reset'})
        self.assertEqual(c,{0});self.assertEqual(o,{})

    def test_supply_nodes_do_not_pull_in_unrelated_capacitance(self):
        p,b,c,o=passive_cut({'X':['a','VPWR']},[('C0','a','VPWR'),('C1','VPWR','remote')],{'X'})
        self.assertEqual(p,{'a'});self.assertEqual(c,{0})

if __name__=='__main__':unittest.main()
