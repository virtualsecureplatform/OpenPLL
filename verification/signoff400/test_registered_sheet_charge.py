from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest
import test_compiled_sheet_charge_cached as cached_tests
from compiled_sheet_charge_registered import build,invoke,payload,decode
from native_axis_basis import axis_template,named_sheet,exact_axis_mass
from floating_sheet_charge import area,constant,line
class RegisteredSheetCharge(cached_tests.CachedCompiledSheetCharge):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=build(Path(cls.temp.name)/'build')
    def test_native_private_node_aliases_match_nonuniform_axis_mass(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cases=[];expected={}
            for axis,box,knots in [(0,[0,0,6,2],[(0,'n0'),(2,'n1'),(6,'n2')]),(1,[0,0,2,6],[(0,'n0'),(2,'n1'),(6,'n2')]),(0,[0,0,6,2],[(0,'merged'),(2,'merged'),(6,'n2')])]:
                t=axis_template(box,axis,knots);name=str(len(cases));reference=exact_axis_mass(box,axis,knots);self.assertEqual(area(named_sheet(t),constant('REF'),box),reference)
                cases.append(dict(id=name,operator=['A',1,0,1,box,1.],source_basis=payload(t,'',point_nodes=t['point_nodes']),target_basis=dict(constant='REF')));expected[name]=reference
            for threads in (1,8):
                rows,_=invoke(self.binary,cases,root/str(threads),threads=threads)
                for row in rows:self.assertEqual(decode(row,exact=True),expected[row['id']])
    def test_shared_nodes_survive_cross_section_and_same_chain_line(self):
        box=[0,0,6,2];knots=[(0,'a'),(2,'b'),(6,'c')];t=axis_template(box,0,knots);basis=named_sheet(t);sp=payload(t,'',point_nodes=t['point_nodes']);a=[1,0,1,2];b=[5,0,5,2]
        expected=line(basis,basis,a,b,1.)
        with tempfile.TemporaryDirectory() as temp:
            rows,_=invoke(self.binary,[dict(id='line',operator=['L',1,1,-1,a,b,1.,1,4],source_basis=sp,target_basis=sp)],Path(temp)/'run');self.assertEqual(decode(rows[0],exact=True),expected)
    def test_missing_axis_coverage_and_mismatched_identity_count_fail(self):
        for knots in ([(1,'a'),(6,'b')],[(-1,'a'),(6,'b')],[(0,'a'),(2,'b'),(2,'c'),(6,'d')]):
            with self.assertRaises(ValueError):axis_template([0,0,6,2],0,knots)
        t=axis_template([0,0,6,2],0,[(0,'a'),(6,'b')])
        with self.assertRaises(ValueError):payload(t,'',point_nodes=['a'])
