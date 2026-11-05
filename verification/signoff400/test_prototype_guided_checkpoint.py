"""Provenance/deadline controls must reject before starting native routing."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common_v3 import sha
from finish_prototype_guided_checkpoint_v1 import run


class GuidedCheckpointGuards(unittest.TestCase):
    def fixture(self, root, *, phase_matches=True, guide_matches=True,
                nonlocal_preserved=True, deadline=0):
        source=root/'source';guides=root/'guides';phase=root/'phase'
        for p in (source,guides,phase):p.mkdir()
        db=source/'antenna_repaired.odb';db.write_bytes(b'native snapshot placeholder')
        original=source/'global.guide';original.write_text('original guide')
        sdc=phase/'enabled_phase.sdc';sdc.write_text('phase constraints')
        receipt=source/'assessment.json'
        receipt.write_text(json.dumps(dict(input_sha256={str(sdc):sha(sdc)} if phase_matches else {},artifacts={})))
        pins={str(p):sha(p) for p in (receipt,db,original)}
        if not guide_matches:pins.pop(str(db))
        (guides/'assessment.json').write_text(json.dumps(dict(input_sha256=pins,artifacts={},
            nonlocal_guide_geometry_preserved=nonlocal_preserved,local_corridors=36)))
        (source/'owner.json').write_text(json.dumps(dict(deadline_uptime=deadline)))
        return source,guides,phase,root/'output'

    def rejected(self, message, **options):
        with tempfile.TemporaryDirectory() as temp:
            args=self.fixture(Path(temp),**options)
            with patch('finish_prototype_guided_checkpoint_v1.execute') as native:
                with self.assertRaisesRegex((ValueError,TimeoutError),message):run(*args)
                native.assert_not_called()
            self.assertFalse(args[-1].exists())

    def test_guides_must_bind_same_native_snapshot(self):
        self.rejected('guide receipt',guide_matches=False)

    def test_phase_must_match_source(self):
        self.rejected('same phase',phase_matches=False)

    def test_nonlocal_geometry_must_be_preserved(self):
        self.rejected('local-only',nonlocal_preserved=False)

    def test_expired_deadline_cannot_be_reset(self):
        self.rejected('original checkpoint deadline expired')


if __name__=='__main__':unittest.main()
