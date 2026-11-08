import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import nullcontext
from test_keeper_TT_characterization import CollectorWorkflow
from common_v3 import save,sha
from collect_keeper_TT_BSIM_corrected import run

class CorrectedCollector(CollectorWorkflow):
    def fixture(self,root):
        family,cases=super().fixture(root)
        binary=root/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce'
        binary.parent.mkdir(parents=True);binary.write_text('synthetic corrected executable')
        for row in cases:
            for name in ['inputs.json','assessment.json']:
                f=Path(row['native'])/name;a=json.loads(f.read_text())
                a.update(native_executable=str(binary),native_executable_sha256=sha(binary),BSIM_PBSWGD_default_corrected=True)
                a['input_sha256'][str(binary)]=sha(binary);save(f,a)
            f=Path(row['physical'])/'assessment.json';a=json.loads(f.read_text())
            a['input_sha256']={str(Path(row['native'])/'assessment.json'):sha(Path(row['native'])/'assessment.json')};save(f,a)
        f=family/'protocol.json';a=json.loads(f.read_text());a['input_sha256'][str(binary)]=sha(binary);save(f,a)
        save(family/'assessment.json',dict(input_sha256={},all_native_controllers_initialized=True,submitted_cases=cases))
        return family,cases

    def collect(self,family,output):
        with patch('collect_keeper_TT_BSIM_corrected.ROOT',family.parent),patch('collect_keeper_TT_BSIM_corrected.os.sched_setaffinity'),patch('collect_keeper_TT_BSIM_corrected.lease',return_value=nullcontext()):
            run(family,output,False)

    def test_old_active_backend_rejected_despite_corrected_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);family,cases=self.fixture(root)
            f=Path(cases[0]['native'])/'inputs.json';a=json.loads(f.read_text());a['native_executable_sha256']='old';save(f,a)
            with self.assertRaisesRegex(ValueError,'active executable'):self.collect(family,root/'result')

    def test_completed_receipt_backend_rechecked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);family,cases=self.fixture(root)
            f=Path(cases[0]['native'])/'assessment.json';a=json.loads(f.read_text());a['BSIM_PBSWGD_default_corrected']=False;save(f,a)
            with self.assertRaisesRegex(ValueError,'active executable'):self.collect(family,root/'result')

if __name__=='__main__':unittest.main()
