from collections import defaultdict
from fractions import Fraction as F
import math
import unittest
from floating_sheet_basis import mesh
from floating_sheet_charge import sheet,constant
from floating_sheet_fringe import fringe,lorentz_moments

def integrate(f,a,b,tol=1e-12):
    def simpson(a,b,fa,fm,fb):return (b-a)*(fa+4*fm+fb)/6
    def recurse(a,b,fa,fm,fb,whole,tolerance,depth):
        m=(a+b)/2;l=(a+m)/2;r=(m+b)/2;fl,fr=f(l),f(r);left=simpson(a,m,fa,fl,fm);right=simpson(m,b,fm,fr,fb);delta=left+right-whole
        if depth==0 or abs(delta)<=15*tolerance:return left+right+delta/15
        return recurse(a,m,fa,fl,fm,left,tolerance/2,depth-1)+recurse(m,b,fm,fr,fb,right,tolerance/2,depth-1)
    fa,fm,fb=f(a),f((a+b)/2),f(b);return recurse(a,b,fa,fm,fb,simpson(a,b,fa,fm,fb),tol,24)
class FloatingSheetFringe(unittest.TestCase):
    def test_high_precision_moments_against_independent_adaptive_integrals(self):
        for near,far,mult in [(0,4,.2),(1,4,.2),(10,11,1e4),(0,1,1e-12),(1999,2000,.1)]:
            moments=lorentz_moments(F(near),F(far),F(mult))
            for power,value in enumerate(moments):
                scale=(far-near)*mult*max(abs(near),abs(far),1)**power/(1+(mult*near)**2)
                expected=scale*integrate(lambda d:mult*d**power/(1+(mult*d)**2)/scale,near,far,tol=1e-13)
                self.assertLessEqual(abs(float(value)-expected),2e-11*max(abs(expected),1e-25),(near,far,mult,power,value,expected))
    def test_all_directions_signed_affine_energy_and_conservation(self):
        for direction in (1,2,4,8):
            normal=0 if direction in (1,4) else 1;along=1-normal;sign=-1 if direction in (1,8) else 1
            box=[-4,0,-1,3] if direction==1 else [1,0,4,3] if direction==4 else [0,1,3,4] if direction==2 else [0,-4,3,-1]
            edge=[0,0,0,3] if normal==0 else [0,0,3,0]
            # Target potential is physical signed normal coordinate + tangent.
            t=mesh([(box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3])],refinement=2);basis=sheet(t,'t')
            v={'s':2.};v.update({'t'+str(i):float(p[normal]+p[along]) for i,p in enumerate(t['points'])})
            expected=integrate(lambda d:.6366*.2/(1+(.2*d)**2)*integrate(lambda u:(2-sign*d-u)**2,0,3),1,4)
            for density in (-2.,2.):
                matrix=fringe(constant('s'),basis,edge,box,direction,density,.2);actual=math.fsum(c*v[a]*v[b] for (a,b),c in matrix.items());self.assertAlmostEqual(actual,density*expected,places=10)
                rows=defaultdict(float)
                for (a,b),c in matrix.items():self.assertEqual(c,matrix.get((b,a)));rows[a]+=c
                self.assertLess(max(map(abs,rows.values())),1e-12)
    def test_constant_collapse_matches_native_arctan_integral_and_zero_multiplier(self):
        for direction,box,edge in [(4,[1,0,4,3],[0,0,0,3]),(8,[0,-4,3,-1],[0,0,3,0])]:
            matrix=fringe(constant('s'),constant('t'),edge,box,direction,2.,.2)
            expected=2*3*.6366*(math.atan(.8)-math.atan(.2));self.assertAlmostEqual(matrix['s','s'],expected,places=13)
            self.assertEqual(fringe(constant('s'),constant('t'),edge,box,direction,2.,0),{})
    def test_source_projection_and_missing_support_are_checked(self):
        t=mesh([(-1,0),(0,0),(0,3),(-1,3)],refinement=2);basis=sheet(t,'s');matrix=fringe(basis,constant('ref'),[0,0,0,3],[1,0,4,3],4,1.,.2)
        v={'ref':0.};v.update({'s'+str(i):float(y) for i,(x,y) in enumerate(t['points'])})
        expected=9*.6366*(math.atan(.8)-math.atan(.2));actual=math.fsum(c*v[a]*v[b] for (a,b),c in matrix.items());self.assertAlmostEqual(actual,expected,places=12)
        with self.assertRaisesRegex(ValueError,'outside'):fringe(basis,constant('ref'),[0,0,0,3],[1,0,4,4],4,1.,.2)
