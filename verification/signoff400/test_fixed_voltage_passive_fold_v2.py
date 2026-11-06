from fractions import Fraction as F
import unittest
from fold_fixed_voltage_passives_v2 import fold
from audit_hierarchical_capacitance import number


class FixedBoundaryFoldTest(unittest.TestCase):
    def fixture(self):
        devices=('.model dtest D\n+ IS=1e-15\n.subckt __openpll_literal_leaf_0 d g s b\n'
                 'Rinternal d g 3\n.ends\nXflat1 out input VPWR VGND __openpll_literal_leaf_0\n'
                 'C1 out fixed1 2e-12\nC2 fixed2 out 1e-12\nC3 out input 3e-12\n'
                 'C4 input out 4e-12\nC5 fixed1 fixed2 1e-12\nC6 out VPWR 1e-12\n'
                 'R1 out fixed1 1000\nR2 fixed2 out 2000\nR3 out input 20\nR4 fixed1 fixed2 3000\n')
        sources=dict(VPWR=('Vpower','1.8'),VGND=('Vground','0'),fixed1=('Vfixed1','1.2'),
                     fixed2=('Vfixed2','-0.2'),input=('Vinput','PULSE(0 1.8 1n 1p 1p 1n 2n)'))
        return devices,sources

    def current(self,text,node,voltages,derivatives):
        depth=0;total=F(0)
        for line in text.splitlines():
            f=line.split()
            if not f:continue
            if f[0].lower()=='.subckt':depth+=1;continue
            if f[0].lower()=='.ends':depth-=1;continue
            if depth or f[0][0]not in 'RCI':continue
            a,b=f[1:3];v=number(f[3])
            if f[0][0]=='C':current=v*(derivatives[a]-derivatives[b])
            elif f[0][0]=='R':current=(voltages[a]-voltages[b])/v
            else:current=v
            if a==node:total+=current
            if b==node:total-=current
        return total

    def test_retained_KCL_and_nonlinear_cards_preserved(self):
        original,sources=self.fixture();new,source_text,report=fold(original,sources)
        self.assertIn('Xflat1 out input VPWR VGND __openpll_literal_leaf_0\n',new)
        self.assertIn('.model dtest D\n+ IS=1e-15\n',new)
        self.assertIn('Rinternal d g 3\n',new)
        self.assertNotIn('Vfixed1 ',source_text);self.assertIn('Vpower VPWR 0 1.8',source_text)
        for out in (F(0),F(1,2),F(9,5)):
            voltages=dict(out=out,input=F(9,10),VPWR=F(9,5),VGND=F(0),fixed1=F(6,5),fixed2=F(-1,5))
            voltages['0']=F(0)
            derivatives={k:F(0)for k in voltages};derivatives.update(out=F(10**9),input=F(-2*10**8))
            for node in ('out','input'):
                self.assertLess(abs(float(self.current(original,node,voltages,derivatives)-self.current(new,node,voltages,derivatives))),1e-15)
        self.assertTrue(report['retained_node_equations_exact_before_serialization'])
        self.assertFalse(report['native_response_equivalence_qualified'])

    def test_explicit_signed_C_retains_nodal_currents(self):
        original,sources=self.fixture();original+='Cnegative out input -8e-12\n'
        new,_,report=fold(original,sources,allow_signed_capacitors=True)
        voltages={n:F(0)for n in ('out','input','VPWR','VGND','fixed1','fixed2','0')}
        voltages.update(out=F(1,2),input=F(9,10),VPWR=F(9,5),fixed1=F(6,5),fixed2=F(-1,5))
        derivatives={n:F(0)for n in voltages};derivatives.update(out=F(10**9),input=F(-2*10**8))
        self.assertLess(abs(float(self.current(original,'out',voltages,derivatives)-self.current(new,'out',voltages,derivatives))),1e-15)
        self.assertFalse(report['passive_coefficients_nonnegative'])
        with self.assertRaises(ValueError):fold(original.replace('1000','-1000'),sources,allow_signed_capacitors=True)

    def test_dynamic_boundary_and_zero_R_source_remain(self):
        devices,sources=self.fixture();sources['fixed1']=('Vfixed1','PWL FILE "fixed.pwl"')
        new,source_text,_=fold(devices+'Rzero out fixed2 0\n',sources)
        self.assertIn('Vfixed1 fixed1 0 PWL',source_text)
        self.assertIn('Vfixed2 fixed2 0 -0.2',source_text)
        self.assertIn('Rzero out fixed2 0',new)

    def test_negative_or_parameterized_passives_rejected(self):
        devices,sources=self.fixture()
        for damaged in (devices.replace('2e-12','-2e-12'),devices.replace('1000','-1000'),devices+'Cextra out input 1p IC=1\n',devices+'Cextra out input 1p\n+ IC=1\n'):
            with self.subTest(damaged=damaged),self.assertRaises(ValueError):fold(damaged,sources)


if __name__=='__main__':unittest.main()
