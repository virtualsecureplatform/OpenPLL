import unittest
from audit_keeper_flat_MOS_region_join import Aliases, signature

class RegionJoinTests(unittest.TestCase):
    def test_transitive_aliases_and_diffusion_reversal(self):
        a=Aliases(); a.union('VNB','body'); a.union('body','VGND')
        self.assertEqual(signature('nfet','0.15','1','VNB','G',['D','VGND'],a), signature('NFET','3/20','1','vgnd','g',['body','d'],a))
    def test_gate_and_body_are_not_interchangeable(self):
        a=Aliases()
        self.assertNotEqual(signature('nfet','1','2','B','G',['D','S'],a),signature('nfet','1','2','G','B',['D','S'],a))
    def test_dimensions_are_part_of_identity(self):
        a=Aliases()
        self.assertNotEqual(signature('nfet','1','2','B','G',['D','S'],a),signature('nfet','1','3','B','G',['D','S'],a))

if __name__=='__main__': unittest.main()
