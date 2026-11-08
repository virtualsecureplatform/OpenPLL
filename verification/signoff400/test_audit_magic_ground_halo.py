import unittest,tempfile,json
from pathlib import Path
from magic_fringe_kernel import measure
from audit_magic_ground_halo import audit
class GroundHalo(unittest.TestCase):
    def rows(self):
        frac=measure([0,0,50,10],[0,0,0,10],4,.02)/10
        b=dict(cell='top',epoch=1,node_id='A',other_node_id='B',boundary=[0,0,0,10],box=[0,0,50,10],direction=4,length=10,multiplier_hex=.02.hex(),fraction_hex=frac.hex(),coefficient_hex=.5.hex(),split=False,pointwise_placement_qualified=False,subcap_hex=0.0.hex())
        shield=frac/2;sub=.5*((frac-shield)*10)
        return [dict(b,kind='ground_halo_begin',shield_hex=0.0.hex()),dict(kind='fringe_rule_end',cell='top',epoch=1,node1_id='A',node2_id='B',reference_length=10,substrate_shield_hex=shield.hex()),dict(b,kind='ground_halo_end',shield_hex=shield.hex()),dict(b,kind='ground_halo_subtract',shield_hex=shield.hex(),subcap_hex=sub.hex()),dict(kind='ground_update',cell='top',epoch=1,node_id='A',site='ExtCouple.c:1521',has_before=True,before_hex=10.0.hex(),after_hex=(10-sub).hex())]
    def check(self,r):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace';p.write_text(''.join(json.dumps(x)+'\n' for x in r));return audit(p)
    def test_valid_accumulator_and_subtraction(self):self.assertEqual(self.check(self.rows())['ground_halo_subtractions'],1)
    def test_wrong_rule_accumulation(self):
        r=self.rows();r[1]['substrate_shield_hex']=0.0.hex()
        with self.assertRaisesRegex(ValueError,'accumulator'):self.check(r)
    def test_wrong_geometric_fraction(self):
        r=self.rows();r[0]['fraction_hex']=0.0.hex()
        with self.assertRaisesRegex(ValueError,'geometric'):self.check(r)
    def test_wrong_native_subtraction(self):
        r=self.rows();r[3]['subcap_hex']=0.0.hex()
        with self.assertRaisesRegex(ValueError,'formula'):self.check(r)
    def test_truncation_rejected(self):
        with self.assertRaisesRegex(ValueError,'completed'):self.check(self.rows()[:-1])
if __name__=='__main__':unittest.main()
