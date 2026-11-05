import json
from pathlib import Path
import tempfile
import unittest
from common import sha
from audit_prototype_v3 import audit,CHECKS,PROFILE
from prepare_prototype_analog_reference import subcircuits,closure


class PrototypeControls(unittest.TestCase):
    def test_incomplete_and_diagnostic_physical_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);source=p/'source';source.write_text('fixture')
            candidate=dict(source_sha256={str(source):sha(source)},physical_sha256={str(source):sha(source)})
            receipt=p/'receipt.json'
            r=dict(status='pass',profile_sha256=sha(PROFILE),candidate=candidate,
                input_sha256={str(source):sha(source)},artifacts={str(source):sha(source)},
                gate='physical_integrity',validated_for_prototype=True,checks={k:True for k in CHECKS['physical_integrity']})
            def check():
                receipt.write_text(json.dumps(r));return audit(dict(candidate=candidate,evidence={'physical_integrity':[dict(path=str(receipt),sha256=sha(receipt))]}))
            self.assertEqual(check()['gates']['physical_integrity']['status'],'pass')
            r['checks'].pop('electrical_rules');self.assertEqual(check()['gates']['physical_integrity']['status'],'fail')
            r['checks']['electrical_rules']=True;r['diagnostic']=True
            result=check();self.assertEqual(result['gates']['physical_integrity']['status'],'fail')
            self.assertFalse(result['release_ready']);self.assertFalse(result['production_qualified'])

    def test_analog_closure_preserves_continuations_and_rejects_unresolved_models(self):
        text='.subckt leaf a b\nX1 a b sky130_fd_pr__nfet_01v8\n+ w=1 l=0.15\n.ends\n.subckt top a b\nX1 a b leaf\n.ends\n'
        names,models=closure(subcircuits(text),'top')
        self.assertEqual(names,{'top','leaf'});self.assertEqual(models,{'sky130_fd_pr__nfet_01v8'})
        with self.assertRaises(ValueError):closure(subcircuits(text.replace('a b leaf','a b unknown')),'top')
        with self.assertRaises(ValueError):subcircuits('.subckt open a b\n')


if __name__=='__main__':unittest.main()
