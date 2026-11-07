import tempfile,unittest
from pathlib import Path
from fractions import Fraction as F
from compare_keeper_geometry_primary_C import flat_matrix,differences

class GeometryRestriction(unittest.TestCase):
    def parse(self,text):
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'test.spice';p.write_text(text);return flat_matrix(p)
    def test_signed_alias_restriction_and_floating_annotation(self):
        ports,groups,matrix,counts=self.parse('.subckt top A\n+ VGND\nR0 A alias 0\nC0 alias VGND 4f\nC1 A internal -1f $ **FLOATING\nC2 internal VGND 0\n.ends\n')
        self.assertEqual(ports,['A','VGND']);self.assertEqual(matrix,{(('A',),('A',)):F(3,10**15)});self.assertEqual(counts,dict(positive=1,negative=1,zero=1))
    def test_positive_wire_R_rejected(self):
        with self.assertRaisesRegex(ValueError,'zero-R'):self.parse('.subckt top A VGND\nR0 A internal 1\n.ends\n')
    def test_multiple_tops_rejected(self):
        with self.assertRaisesRegex(ValueError,'one flat top'):self.parse('.subckt a A\n.ends\n.subckt b B\n.ends\n')
    def test_difference_includes_missing_entry_exactly(self):
        key=(('A',),('A',));result=differences({key:F(1,3)},{})
        self.assertEqual(result[0]['right_minus_left_F'],'-1/3')
if __name__=='__main__':unittest.main()
