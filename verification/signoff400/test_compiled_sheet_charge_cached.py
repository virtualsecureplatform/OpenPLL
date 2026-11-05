from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest
from compiled_sheet_charge_cached import build,invoke,payload,decode
from floating_sheet_basis import mesh
from floating_sheet_charge import sheet,constant,area,line
from floating_sheet_fringe import fringe
class CachedCompiledSheetCharge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=build(Path(cls.temp.name)/'build')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def fixture(self):
        t=mesh([(0,0),(3,0),(3,2),(0,2)],refinement=2);s=sheet(t,'s');sp=payload(t,'s');cases=[];references={}
        for density in (2.,-2.):
            for kind in ('A','L'):
                op=[kind,1,0,1,[0,0,3,2],density] if kind=='A' else [kind,1,1,-1,[0,0,0,2],[3,0,3,2],density,1,4]
                name=kind+str(density);target=constant('ref') if kind=='A' else s;tp=dict(constant='ref') if kind=='A' else sp
                references[name]=area(s,target,op[4],density) if kind=='A' else line(s,target,op[4],op[5],density)
                cases.append(dict(id=name,operator=op,source_basis=sp,target_basis=tp))
        for direction in (1,2,4,8):
            normal=0 if direction in (1,4) else 1;box=[-4,0,-1,3] if direction==1 else [1,0,4,3] if direction==4 else [0,1,3,4] if direction==2 else [0,-4,3,-1];edge=[0,0,0,3] if normal==0 else [0,0,3,0]
            u=mesh([(box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3])],refinement=2)
            for density in (-2.,2.):
                name='F'+str(direction)+str(density);op=['F',1,2,3,edge,box,direction,density,.2];cases.append(dict(id=name,operator=op,source_basis=dict(constant='sref'),target_basis=payload(u,'t')));references[name]=fringe(constant('sref'),sheet(u,'t'),edge,box,direction,density,.2)
        return cases,references
    def test_exact_uniform_and_signed_fringe_match_independent_oracles(self):
        cases,reference=self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for threads in (1,2,16):
                rows,summary=invoke(self.binary,cases,root/str(threads),threads=threads)
                self.assertEqual(summary['integrated_cases'],len(cases))
                for r in rows:
                    expected=reference[r['id']]
                    if r['id'][0]!='F':self.assertEqual(decode(r,exact=True),expected)
                    else:
                        actual=decode(r);norm=max(map(abs,expected.values()))
                        for key in set(actual)|set(expected):self.assertLessEqual(abs(actual.get(key,0)-expected.get(key,0)),2e-12*norm)
                        for (a,b),v in actual.items():self.assertEqual(actual.get((b,a)),v)
    def test_parallel_outside_support_fails_without_peer_output(self):
        cases,_=self.fixture();cases[0]['operator'][4]=[-1,0,3,2]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError,'compiled worker failed'):invoke(self.binary,cases,Path(temp)/'failed',threads=8)
            self.assertEqual((Path(temp)/'failed/matrices.jsonl').read_text(),'')
    def test_shared_line_two_meshes_and_exact_coordinate_guard(self):
        t=mesh([(0,0),(3,0),(3,2),(0,2)],refinement=2);u=mesh([(0,4),(3,4),(3,6),(0,6)],refinement=4);a=[0,1,3,1];b=[0,5,3,5]
        cases=[dict(id='line',operator=['L',1,2,1,a,b,.125,0,0],source_basis=payload(t,'s'),target_basis=payload(u,'t'))]
        expected=line(sheet(t,'s'),sheet(u,'t'),a,b,.125)
        with tempfile.TemporaryDirectory() as temp:
            rows,_=invoke(self.binary,cases,Path(temp)/'result');self.assertEqual(decode(rows[0],exact=True),expected)
        with self.assertRaisesRegex(ValueError,'exactly serializable'):payload(dict(points=[(F(1,3),0)],triangles=[]),'s')
    def test_polygon_hole_and_boundary_line_preserve_exact_matrices(self):
        t=mesh([(0,0),(8,0),(8,7),(0,7)],[[(2,2),(4,2),(4,5),(2,5)]])
        source=sheet(t,'sheet');sp=payload(t,'sheet');ops=[['A',1,0,1,[0,0,2,7],.125],['L',1,0,2,[2,2,2,5],[2,2,2,5],.125,1,0]]
        cases=[dict(id=str(i),operator=op,source_basis=sp,target_basis=dict(constant='ref')) for i,op in enumerate(ops)]
        with tempfile.TemporaryDirectory() as temp:
            rows,_=invoke(self.binary,cases,Path(temp)/'result',threads=2)
            for r,op in zip(rows,ops):
                expected=area(source,constant('ref'),op[4],op[5]) if op[0]=='A' else line(source,constant('ref'),op[4],op[5],op[6])
                self.assertEqual(decode(r,exact=True),expected)

    def test_translation_renaming_density_and_alias_relations(self):
        import copy
        t=mesh([(0,0),(3,0),(3,2),(0,2)]);sp=payload(t,'s')
        base=dict(id='original',operator=['A',1,0,1,[0,0,3,2],1.],source_basis=sp,target_basis=dict(constant='ref'))
        moved=copy.deepcopy(base);moved['id']='translated';moved['source_basis']['prefix']='new';moved['target_basis']['constant']='newref';moved['operator'][3]=999
        for p in moved['source_basis']['points']:p[0]+=1000;p[1]-=2000
        moved['operator'][4]=[1000,-2000,1003,-1998]
        same=copy.deepcopy(base);same['id']='self';same['target_basis']=copy.deepcopy(sp)
        distinct=copy.deepcopy(same);distinct['id']='other';distinct['target_basis']['prefix']='t'
        renamed=copy.deepcopy(distinct);renamed['id']='renamed';renamed['target_basis']['prefix']='u'
        den=copy.deepcopy(base);den['id']='density';den['operator'][5]=2.
        cases=[base,moved,same,distinct,renamed,den]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cached,stats=invoke(self.binary,cases,root/'cached',threads=1);plain,_=invoke(self.binary,cases,root/'plain',threads=1,cache_mib=0)
            self.assertEqual(cached,plain);self.assertGreaterEqual(stats['cache_hits'],2);self.assertEqual(decode(cached[2],exact=True),{});self.assertTrue(decode(cached[3],exact=True))
            self.assertEqual({k:2*v for k,v in decode(cached[0],exact=True).items()},decode(cached[-1],exact=True))
    def test_cache_eviction_preserves_values_and_stays_bounded(self):
        cases,_=self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);small,stats=invoke(self.binary,cases*3,root/'small',threads=2,cache_mib=.025);plain,_=invoke(self.binary,cases*3,root/'plain',threads=2,cache_mib=0)
            self.assertEqual(small,plain);self.assertGreater(stats['cache_misses'],0);self.assertLessEqual(stats['cache_estimate_limit_bytes_per_thread'],26215);self.assertGreater(stats['cache_clears'],0)
    def test_mixed_coefficients_directions_translations_and_namespaces(self):
        import copy
        base,_=self.fixture();cases=[]
        for i in range(96):
            item=copy.deepcopy(base[i%len(base)]);item['id']=str(i);dx,dy=(i%7)*1000,-(i%11)*300
            seen=set()
            for basis in (item['source_basis'],item['target_basis']):
                if id(basis) in seen:continue
                seen.add(id(basis))
                if 'constant' in basis:basis['constant']='ref_'+str(i)
                else:
                    # Preserve sharing for same-sheet cases while changing
                    # names independently between separate integration cases.
                    basis['prefix']=basis['prefix']+'_'+str(i)+'_'
                    for p in basis['points']:p[0]+=dx;p[1]+=dy
            op=item['operator'];op[3]=i+10000
            for index in ([4] if op[0]=='A' else [4,5]):
                op[index]=[op[index][0]+dx,op[index][1]+dy,op[index][2]+dx,op[index][3]+dy]
            density_index=5 if op[0]=='A' else 6 if op[0]=='L' else 7;op[density_index]*=1+(i%3)*.125
            if op[0]=='F':op[8]*=1+(i%4)*.25
            cases.append(item)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cached,stats=invoke(self.binary,cases*2,root/'cached',threads=8);plain,_=invoke(self.binary,cases*2,root/'plain',threads=8,cache_mib=0)
            self.assertEqual(cached,plain);self.assertGreater(stats['cache_hits'],0)
    def test_extreme_fringe_panels_match_high_precision_reference(self):
        from test_compiled_sheet_charge import CompiledSheetCharge
        CompiledSheetCharge.test_fringe_extreme_ranges_and_panel_refinement(self)
