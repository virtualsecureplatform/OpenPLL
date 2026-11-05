from collections import defaultdict
from fractions import Fraction as F
import unittest
from floating_sheet_basis import mesh,energy
from floating_sheet_charge import sheet,constant,area,line
class FloatingSheetCharge(unittest.TestCase):
    def basis(self,n=1,prefix='s'):
        t=mesh([(0,0),(3,0),(3,2),(0,2)],refinement=n);return t,sheet(t,prefix)
    def voltage(self,t,prefix,a,b,c):return {prefix+str(i):a*x+b*y+c for i,(x,y) in enumerate(t['points'])}
    def check_conservation(self,matrix):
        rows=defaultdict(F)
        for (a,b),v in matrix.items():self.assertEqual(matrix.get((b,a),0),v);rows[a]+=v
        self.assertTrue(all(v==0 for v in rows.values()))
    def test_ground_area_exact_linear_energy_signed_terms_and_collapse(self):
        for n in (1,2,4):
            t,s=self.basis(n);v=self.voltage(t,'s',1,2,3);v['ref']=0
            # Independent tensor-product integral of (x+2y+3)^2 on [0,3]x[0,2].
            expected=F(3**3*2,3)+4*F(3*2**3,3)+9*6+4*F(3**2*2**2,4)+6*F(3**2*2,2)+12*F(3*2**2,2)
            for density in (F(2),F(-2),F(1,7)):
                m=area(s,constant('ref'),[0,0,3,2],density);self.check_conservation(m);self.assertEqual(energy(m,v),density*expected)
                collapsed={k:F(k!='ref') for k in v};self.assertEqual(energy(m,collapsed),density*6)
    def test_two_independent_meshes_and_identical_field_area(self):
        t,s=self.basis(2,'s');u,b=self.basis(4,'t');v=self.voltage(t,'s',2,1,3);v.update(self.voltage(u,'t',1,1,3))
        m=area(s,b,[0,0,3,2]);self.check_conservation(m);self.assertEqual(energy(m,v),F(3**3*2,3))
        self.assertEqual(area(s,s,[0,0,3,2]),{})
    def test_finite_R_self_line_energy_survives_ideal_collapse(self):
        for n in (1,2,4):
            t,s=self.basis(n);v=self.voltage(t,'s',1,0,0);m=line(s,s,[0,0,0,2],[3,0,3,2],2);self.check_conservation(m)
            self.assertEqual(energy(m,v),36);self.assertEqual(energy(m,{k:F(1) for k in v}),0)
    def test_internal_shared_edge_reference_line_and_outside_support(self):
        t,s=self.basis(2);v=self.voltage(t,'s',0,1,0);v['ref']=0
        m=line(s,constant('ref'),[F(3,2),0,F(3,2),2],[0,0,0,2]);self.check_conservation(m);self.assertEqual(energy(m,v),F(8,3))
        with self.assertRaisesRegex(ValueError,'outside'):area(s,constant('ref'),[-1,0,3,2])
        with self.assertRaisesRegex(ValueError,'outside'):line(s,constant('ref'),[-1,0,-1,2],[0,0,0,2])
