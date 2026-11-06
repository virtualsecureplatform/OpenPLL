"""Isolated copy/identity controls; mocked gates never qualify a real candidate."""
import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from common_v3 import sha
from package_prototype_v3 import ROLES,run as legacy_stage
from package_prototype_v4 import run as stage
from check_portable_prototype_inventory_v2 import check

class CandidateHandoffCompletenessTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.sources=[self.root/f'selected_{i}.v' for i in range(9)]
        for i,p in enumerate(self.sources):p.write_bytes(f'// selected physical source {i}\n'.encode())
        self.gds=self.root/'physical.gds';self.gds.write_bytes(b'physical fixture\x00\n')
        pins={str(p):sha(p) for p in self.sources+[self.gds]}
        self.evidence=self.root/'evidence.json';self.evidence.write_text(json.dumps(dict(input_sha256=pins,artifacts=pins)))
        gates=['physical_integrity','analog_models_and_tuning','digital_timing_and_cdc','closed_loop_operation','reproducible_handoff']
        self.audit=dict(identity_failures=[],gates={g:dict(status='pass') for g in gates})
        artifacts={role:[dict(source=str(self.sources[0]),destination=role+'/fixture')] for role in ROLES}
        artifacts['rtl']=[dict(source=str(p),destination='rtl/'+p.name) for p in self.sources]
        artifacts['gds']=[dict(source=str(self.gds),destination='gds/physical.gds')]
        self.data=dict(candidate=dict(source_sha256={str(p):sha(p) for p in self.sources},physical_sha256={str(self.gds):sha(self.gds)}),evidence={g:[dict(path=str(self.evidence),sha256=sha(self.evidence))] for g in gates},handoff_artifacts=artifacts)
        self.manifest=self.root/'manifest.json'
    def write(self):self.manifest.write_text(json.dumps(self.data))
    def test_complete_candidate_survives_relocation_without_original_sources(self):
        self.write();output=self.root/'package'
        with patch('package_prototype_v4.audit',return_value=self.audit):stage(self.manifest,output)
        receipt=sha(output/'assessment.json');relocated=self.root/'relocated';shutil.move(output,relocated)
        for p in self.sources+[self.gds,self.evidence,self.manifest]:p.unlink()
        r=check(relocated,receipt)
        self.assertTrue(r['candidate_rtl_complete']);self.assertTrue(r['candidate_physical_complete']);self.assertFalse(r['source_paths_opened']);self.assertFalse(r['release_ready'])
        for i in range(9):self.assertEqual((relocated/f'rtl/selected_{i}.v').read_bytes(),f'// selected physical source {i}\n'.encode())
        script=self.root/'portable_checker.py'
        shutil.copyfile(Path(__file__).with_name('check_portable_prototype_inventory_v2.py'),script)
        command=[sys.executable,'-I',str(script),str(relocated),'--receipt-sha256',receipt]
        result=subprocess.run(command,cwd=self.root,env={'PATH':'/usr/bin:/bin'},capture_output=True,text=True,check=True)
        self.assertTrue(json.loads(result.stdout)['candidate_rtl_complete'])
    def test_nonempty_RTL_role_cannot_omit_one_candidate_source(self):
        self.data['handoff_artifacts']['rtl'].pop();self.write();output=self.root/'package'
        with patch('package_prototype_v4.audit',return_value=self.audit),self.assertRaisesRegex(ValueError,'candidate rtl identities missing'):stage(self.manifest,output)
        self.assertFalse(output.exists())
    def test_qualified_file_in_wrong_physical_role_is_rejected(self):
        self.data['handoff_artifacts']['gds'][0]['source']=str(self.sources[0]);self.write();output=self.root/'package'
        with patch('package_prototype_v4.audit',return_value=self.audit),self.assertRaisesRegex(ValueError,'candidate gds identities missing'):stage(self.manifest,output)
        self.assertFalse(output.exists())
    def test_standalone_checker_rejects_incomplete_legacy_stage(self):
        for role in ['rtl','gds']:
            with self.subTest(role=role):
                original=self.data['handoff_artifacts'][role]
                self.data['handoff_artifacts'][role]=original[:-1] if role=='rtl' else [dict(source=str(self.sources[0]),destination='gds/fixture')]
                self.write();output=self.root/('legacy_'+role)
                with patch('package_prototype_v3.audit',return_value=self.audit):legacy_stage(self.manifest,output)
                with self.assertRaisesRegex(ValueError,'incomplete candidate '+role+' inventory'):check(output,sha(output/'assessment.json'))
                self.data['handoff_artifacts'][role]=original

if __name__=='__main__':unittest.main()
