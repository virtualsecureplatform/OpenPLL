import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from replay_selected_receiver_root_frame_v2 import receiver_reference

class ReceiverReferenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.case=self.root/'case';self.model=self.root/'model'
        (self.case/'native').mkdir(parents=True);self.manifest=self.case/'native/manifest.json';self.manifest.write_text('{}')
    def receipt(self,name,**changes):
        p=self.root/name/'assessment.json';p.parent.mkdir()
        data=dict(selected_physical_RTL_receiver_replayed=True,publication_model=str(self.model),input_sha256={str(self.manifest):sha(self.manifest)},second_stage_records=[{}]);data.update(changes);p.write_text(json.dumps(data));return p
    def test_arbitrary_path_selected_by_bound_case(self):
        valid=self.receipt('independent_DN');wrong=self.receipt('old_UP',input_sha256={'another_manifest':'other'})
        self.assertEqual(receiver_reference([wrong,valid],self.case,self.model)[0],valid)
    def test_ambiguous_receipts_rejected(self):
        with self.assertRaises(ValueError):receiver_reference([self.receipt('a'),self.receipt('b')],self.case,self.model)
    def test_model_and_complete_stage_binding_required(self):
        for change in [dict(publication_model='different'),dict(second_stage_records=[]),dict(selected_physical_RTL_receiver_replayed=False)]:
            with self.subTest(change=change):
                p=self.receipt('receipt'+str(len(list(self.root.iterdir()))),**change)
                with self.assertRaises(ValueError):receiver_reference([p],self.case,self.model)

if __name__=='__main__':unittest.main()
