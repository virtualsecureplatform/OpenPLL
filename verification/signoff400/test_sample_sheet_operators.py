import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT,save
class SampleSheetOperators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'sample';subprocess.run(['g++','-std=c++20','-O2',str(ROOT/'tools/native_rc_coverage/sample_sheet_operators_v3.cpp'),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def invoke(self,root,fault=None):
        save(root/'fields.json',[['@SUBSTRATE_REFERENCE','reference','reference'],['FLOAT','metal1','metal1'],['OTHER','metal1','metal1']]);save(root/'map.json',[0,1,2])
        rows=[dict(original_conductor=name,field_ids=[i],candidate_polygons=1,native_area_equal=fault!='geometry',native_perimeter_equal=True,spatial_material_equal=True,duplicate_component_box=False,rectangle=True,bbox_gds_dbu=[0,0,15,10]) for i,name in ((1,'FLOAT'),(2,'OTHER'))]
        (root/'geometry.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        ops=[['A',1,0,1,[0,0,3,2],2.],['A',1,0,2,[0,0,3,2],-2.],['L',1,1,-7,[0,0,0,2],[3,0,3,2],1.,1,4],['F',1,2,3,[0,0,0,2],[1,0,3,2],4,.3,.2]]
        if fault=='map':ops[0][1]=200
        (root/'ops.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in ops))
        save(root/'config.json',dict(fields=str(root/'fields.json'),field_map=str(root/'map.json'),geometry_partitions=[dict(nodes=str(root/'geometry.jsonl'),native_type='m1')],operators=str(root/'ops.jsonl'),output=str(root/'native'),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30,max_records=20,per_bucket=2))
        return subprocess.run([str(self.binary),str(root/'config.json')],capture_output=True,text=True)
    def test_real_indexed_fields_and_signed_restored_categories(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=self.invoke(root);self.assertEqual(p.returncode,0,p.stderr);r=json.loads((root/'native/summary.json').read_text());self.assertEqual(r['selected_cases'],4);self.assertEqual(r['geometry_conductors'],2)
            rows=[json.loads(s) for s in (root/'native/cases.jsonl').read_text().splitlines()];self.assertEqual(rows[2]['category'],'L/positive/same_sheet/restored');self.assertEqual(rows[2]['source']['original_conductor'],rows[2]['target']['original_conductor']);self.assertEqual(rows[0]['source']['global_field_id'],1)
    def test_invalid_mapping_and_geometry_are_rejected(self):
        for fault in ('map','geometry'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);self.assertNotEqual(self.invoke(root,fault).returncode,0);self.assertFalse((root/'native/summary.json').exists())

    def test_separated_windows_keep_exact_offsets_and_unique_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.invoke(root)
            import shutil
            shutil.rmtree(root/'native')
            cfg=json.loads((root/'config.json').read_text());cfg['windows']=4;save(root/'config.json',cfg)
            p=subprocess.run([str(self.binary),str(root/'config.json')],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
            rows=[json.loads(s) for s in (root/'native/cases.jsonl').read_text().splitlines()];self.assertEqual(len(rows),4);self.assertEqual(len({r['operator_byte_offset'] for r in rows}),4)
            with (root/'ops.jsonl').open('rb') as stream:
                for r in rows:
                    stream.seek(r['operator_byte_offset']);self.assertEqual(json.loads(stream.readline()),r['operator'])
