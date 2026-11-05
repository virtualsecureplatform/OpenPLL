import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT,save
class RCCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'inventory'
        subprocess.run(['g++','-std=c++20','-O2',str(ROOT/'tools/native_rc_coverage/main.cpp'),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def fixture(self,root):
        save(root/'fields.json',[['@SUBSTRATE_REFERENCE','reference','reference'],['A','metal1','metal1'],['B','metal2','metal2'],['FLOAT','metal3','metal3']])
        groups=[dict(native_group_id=str(i),original_conductor=label) for i,label in [(1,'A'),(2,'B'),(3,'B')]]
        tiles=[dict(native_group_id='1',original_conductor='A',native_working_plane='metal1',raw_material='metal1')]
        for name,rows in [('groups',groups),('tiles',tiles)]:
            (root/(name+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
        save(root/'cfg.json',dict(fields=str(root/'fields.json'),groups=str(root/'groups.jsonl'),tiles=str(root/'tiles.jsonl'),output=str(root/'native'),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30))
    def invoke(self,root):return subprocess.run([str(self.binary),str(root/'cfg.json')],capture_output=True,text=True)
    def test_all_snapshots_missing_conductors_and_raw_signatures(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root);p=self.invoke(root);self.assertEqual(p.returncode,0,p.stderr)
            r=json.loads((root/'native/summary.json').read_text());self.assertEqual(r['native_snapshots'],3)
            for key in ('explicit_reference','one_native_snapshot','multiple_native_snapshots','no_exact_native_conductor_label','raw_plane_material_signature_present'):self.assertEqual(r['counts'][key],1)
            self.assertFalse(r['physical_domain_complete']);self.assertFalse(r['runtime_model_eligible'])
            rows=[json.loads(s) for s in (root/'native/fields.jsonl').read_text().splitlines()];self.assertEqual([r['field_id'] for r in rows],list(range(4)));self.assertEqual(rows[2]['native_snapshot_count'],2)
    def test_duplicate_snapshot_and_unknown_tile_fail(self):
        for fault in ('duplicate','unknown','field','reference'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);self.fixture(root)
                if fault=='duplicate':
                    p=root/'groups.jsonl';p.write_text(p.read_text()+p.read_text().splitlines()[0]+'\n')
                elif fault=='unknown':
                    p=root/'tiles.jsonl';p.write_text(p.read_text().replace('"1"','"999"'))
                else:
                    p=root/'fields.json';d=json.loads(p.read_text());d=d+[d[-1]] if fault=='field' else d[1:];save(p,d)
                self.assertNotEqual(self.invoke(root).returncode,0);self.assertFalse((root/'native/summary.json').exists())

    def test_controller_lineage_and_mutated_artifacts(self):
        from inventory_rc_coverage import run
        from common import sha
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            charge,domain,index,export=(root/n for n in ('charge','domain','index','export'))
            for p in (charge,domain,index,export):p.mkdir()
            gds=root/'view.gds';gds.write_text('geometry fixture')
            (domain/'trace').mkdir();provenance=domain/'trace/R_provenance.log';provenance.write_text('native fixture')
            (charge/'fields.json').write_bytes((root/'fields.json').read_bytes())
            (index/'tile_domains.jsonl').write_bytes((root/'tiles.jsonl').read_bytes())
            (export/'native').mkdir();(export/'native/groups.jsonl').write_bytes((root/'groups.jsonl').read_bytes())
            save(domain/'assessment.json',dict(input_sha256={str(gds):sha(gds)},artifacts={str(provenance):sha(provenance)}))
            shared={str(domain/'assessment.json'):sha(domain/'assessment.json'),str(gds):sha(gds),str(provenance):sha(provenance)}
            for name,p,artifact in [('charge',charge,charge/'fields.json'),('index',index,index/'tile_domains.jsonl'),('export',export,export/'native/groups.jsonl')]:
                proof=dict(input_sha256=shared,artifacts={str(artifact):sha(artifact)})
                if name=='index':proof.update(native_groups=3,original_conductors=2,domain_counts=dict(domains=1))
                save(p/'assessment.json',proof)
            result=run(charge,domain,index,export,root/'valid');self.assertEqual(result['fields'],4);self.assertFalse(result['full_native_inputs_rehashed'])
            p=charge/'assessment.json';proof=json.loads(p.read_text());proof['input_sha256'][str(gds)]='0'*64;save(p,proof)
            with self.assertRaisesRegex(ValueError,'geometry hashes differ'):run(charge,domain,index,export,root/'wrong_geometry')
            proof['input_sha256'][str(gds)]=sha(gds);save(p,proof)
            with (charge/'fields.json').open('a') as f:f.write('changed')
            with self.assertRaisesRegex(ValueError,'consumed input changed'):run(charge,domain,index,export,root/'mutated')
