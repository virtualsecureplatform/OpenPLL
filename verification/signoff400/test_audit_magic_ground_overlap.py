import unittest,tempfile,json
from pathlib import Path
from audit_magic_ground_overlap import audit
class GroundOverlap(unittest.TestCase):
    def rows(self):
        base=dict(cell='top',epoch=1,overlap_id=1,native_area=20)
        return [dict(base,kind='overlap_support_end',node1_id='A',split=False),dict(base,kind='ground_overlap_subtraction',node_id='A',coefficient_hex=0.5.hex(),pointwise_placement_qualified=False),dict(kind='ground_update',cell='top',epoch=1,node_id='A',site='ExtCouple.c:522',has_before=True,before_hex=11.0.hex(),after_hex=1.0.hex())]
    def check(self,rows):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace';p.write_text(''.join(json.dumps(r)+'\n' for r in rows));return audit(p)
    def test_link_and_arithmetic(self):self.assertEqual(self.check(self.rows())['ground_overlap_subtractions'],1)
    def test_wrong_support_rejected(self):
        r=self.rows();r[1]['overlap_id']=2
        with self.assertRaisesRegex(ValueError,'identity'):self.check(r)
    def test_wrong_arithmetic_and_truncation_rejected(self):
        r=self.rows();r[2]['after_hex']=2.0.hex()
        with self.assertRaisesRegex(ValueError,'arithmetic'):self.check(r)
        with self.assertRaisesRegex(ValueError,'completed'):self.check(self.rows()[:-1])
if __name__=='__main__':unittest.main()
