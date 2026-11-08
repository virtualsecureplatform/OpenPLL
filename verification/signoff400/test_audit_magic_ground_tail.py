import unittest,math,tempfile,json
from pathlib import Path
from audit_magic_ground_tail import tail,audit
class GroundTail(unittest.TestCase):
    def row(self,direction=4):
        edge=[0,0,0,10] if direction in [1,4] else [0,0,10,0]
        clip={1:[-50,0,0,10],4:[0,0,50,10],2:[0,0,10,50],8:[0,-50,10,0]}[direction]
        m=.5;f=.6366*math.atan(m*50);c=.2
        return dict(kind='ground_halo_tail',cell='top',epoch=1,node_id='A',boundary=edge,clip=clip,direction=direction,length=10,distance=50,native_float_multiplier_hex=m.hex(),fraction_hex=f.hex(),coefficient_hex=c.hex(),subcap_hex=((c*(1-f))*10).hex(),split=False,pointwise_placement_qualified=False)
    def test_four_directions(self):
        for d in [1,2,4,8]:self.assertGreater(tail(self.row(d)),0)
    def test_wrong_geometry_and_fraction_rejected(self):
        r=self.row();r['distance']=49
        with self.assertRaisesRegex(ValueError,'geometry'):tail(r)
        r=self.row();r['fraction_hex']=0.0.hex()
        with self.assertRaisesRegex(ValueError,'fraction'):tail(r)
    def test_multiplier_must_represent_native_float(self):
        r=self.row();r['native_float_multiplier_hex']=.1.hex()
        with self.assertRaisesRegex(ValueError,'native float'):tail(r)
    def test_exact_ground_update_and_truncation(self):
        r=self.row();s=float.fromhex(r['subcap_hex']);u=dict(kind='ground_update',cell='top',epoch=1,node_id='A',site='ExtCouple.c:1254',has_before=True,before_hex=10.0.hex(),after_hex=(10-s).hex())
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace';p.write_text(json.dumps(r)+'\n'+json.dumps(u)+'\n');self.assertEqual(audit(p)['halo_tail_events'],1)
            p.write_text(json.dumps(r)+'\n')
            with self.assertRaisesRegex(ValueError,'completed'):audit(p)
if __name__=='__main__':unittest.main()
