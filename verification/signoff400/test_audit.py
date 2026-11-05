import copy
import json
from pathlib import Path
import tempfile
import unittest

from common import PROFILE, save, sha, source_pins
from audit import audit, receipt


class AuditControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        physical=self.root/'layout.gds';physical.write_bytes(b'test fixture, not real GDS')
        self.candidate=dict(source_sha256=source_pins(),physical_sha256={str(physical):sha(physical)})
        self.manifest=dict(candidate=self.candidate,evidence={})

    def test_missing_evidence_never_qualifies(self):
        result=audit(self.manifest)
        self.assertFalse(result['release_qualified'])
        self.assertTrue(all(not gate['passed'] for gate in result['gates'].values()))

    def test_diagnostic_stale_profile_and_artifact_changes_rejected(self):
        artifact=self.root/'native.txt';artifact.write_text('fixture')
        report=dict(profile_sha256=sha(PROFILE),candidate_source_sha256=self.candidate['source_sha256'],
                    candidate_physical_sha256=self.candidate['physical_sha256'],
                    input_sha256={str(PROFILE):sha(PROFILE)},artifacts={str(artifact):sha(artifact)},
                    dco_model_qualified=True)
        for change in (dict(diagnostic=True),dict(synthetic=True),dict(profile_sha256='0'*64),
                       dict(candidate_physical_sha256={}),dict(artifacts={}),dict(dco_model_qualified=False)):
            path=self.root/'receipt.json';save(path,dict(report,**change))
            with self.assertRaises(ValueError):receipt(path,sha(path),self.candidate,'dco_model_qualified')
        path=self.root/'receipt.json';save(path,report)
        artifact.write_text('changed')
        with self.assertRaises(ValueError):receipt(path,sha(path),self.candidate,'dco_model_qualified')

    def test_single_point_cannot_qualify_temperature_grid(self):
        artifact=self.root/'native.txt';artifact.write_text('fixture')
        path=self.root/'receipt.json'
        report=dict(profile_sha256=sha(PROFILE),candidate_source_sha256=self.candidate['source_sha256'],
                    candidate_physical_sha256=self.candidate['physical_sha256'],
                    input_sha256={str(PROFILE):sha(PROFILE)},artifacts={str(artifact):sha(artifact)},
                    dco_model_qualified=True,corner='tt',temperature_c=27,supply_v=1.8)
        save(path,report)
        self.manifest['evidence']['dco_model']=[dict(path=str(path),sha256=sha(path))]
        result=audit(self.manifest)
        self.assertFalse(result['gates']['dco_model']['passed'])
        self.assertIn('qualified PVT coverage 1/15',result['gates']['dco_model']['failures'])
        self.assertFalse(result['release_qualified'])


if __name__=='__main__':unittest.main()
