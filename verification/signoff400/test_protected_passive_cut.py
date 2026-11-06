import unittest
from protected_passive_cut import passive_cut
from plan_selected_detector_passive_cut import passive_cut as original

class ProtectedOutputCutTest(unittest.TestCase):
    def test_unprotected_behavior_unchanged(self):
        terms={'driver':['out','in','0'],'load':['far','side','0']};cards=[('R1','out','mid'),('R2','mid','far'),('C1','out','float'),('C2','float','side')]
        self.assertEqual(passive_cut(terms,cards,{'driver'},{'in'}),original(terms,cards,{'driver'},{'in'}))
    def test_output_wire_becomes_unknown_and_omitted_load_remains_explicit(self):
        terms={'driver':['out','in','0'],'load':['far','tip','side','0']};cards=[('R1','out','mid'),('R2','mid','far'),('R3','far','tip'),('C1','far','float'),('C2','float','side')]
        private,boundary,retained,omitted=passive_cut(terms,cards,{'driver'},{'in'},{'out','mid','far','tip'})
        self.assertTrue({'out','mid','far','tip','float'}<=private);self.assertEqual(boundary,{'in','side'});self.assertEqual(retained,set(range(5)));self.assertEqual(omitted,{'load':['far','tip']})
    def test_cannot_release_an_intended_source(self):
        with self.assertRaises(ValueError):passive_cut({'driver':['out','in']},[],{'driver'},{'in'},{'in'})

if __name__=='__main__':unittest.main()
