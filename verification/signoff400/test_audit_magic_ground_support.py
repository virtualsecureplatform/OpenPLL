import unittest,tempfile,json
from pathlib import Path
from audit_magic_ground_support import support,audit

class GroundSupport(unittest.TestCase):
    def row(self,**kw):
        r=dict(kind='ground_support',cell='top',epoch=1,node_id='A',site='area',tile=[0,0,10,20],clip=None,neighbor=None,split=False,neighbor_split=False,direction=-1,measure_kind='area',native_measure_hex=200.0.hex(),coefficient_hex=0.5.hex(),pointwise_placement_qualified=False);r.update(kw);return r
    def test_clipped_area(self):
        self.assertEqual(support(self.row(clip=[5,5,30,30],native_measure_hex=75.0.hex()))['measure'],75)
    def test_clipped_horizontal_edge(self):
        r=self.row(measure_kind='edge_length',direction=2,neighbor=[2,20,30,40],clip=[5,0,8,30],native_measure_hex=3.0.hex())
        self.assertEqual(support(r)['box'],[5,20,8,20])
    def test_wrong_measure_and_nonadjacent_neighbor_rejected(self):
        with self.assertRaisesRegex(ValueError,'measure mismatch'):support(self.row(native_measure_hex=201.0.hex()))
        with self.assertRaisesRegex(ValueError,'nonadjacent'):support(self.row(measure_kind='edge_length',direction=2,neighbor=[0,21,10,40]))
    def test_split_area_accounted_but_unqualified(self):
        self.assertFalse(support(self.row(split=True,native_measure_hex=100.0.hex()))['rectilinear_support_verified'])
    def test_adjacent_native_update_required_and_checked(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace';r=self.row();u=dict(kind='ground_update',cell='top',epoch=1,node_id='A',site='area',has_before=True,before_hex=1.0.hex(),after_hex=101.0.hex())
            p.write_text(json.dumps(r)+'\n'+json.dumps(u)+'\n');self.assertTrue(audit(p)['native_support_measures_and_additions_verified'])
            u['after_hex']=102.0.hex();p.write_text(json.dumps(r)+'\n'+json.dumps(u)+'\n')
            with self.assertRaisesRegex(ValueError,'arithmetic mismatch'):audit(p)
            p.write_text(json.dumps(r)+'\n')
            with self.assertRaisesRegex(ValueError,'complete'):audit(p)
if __name__=='__main__':unittest.main()
