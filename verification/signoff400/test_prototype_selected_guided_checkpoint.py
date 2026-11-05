import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common_v3 import sha
from finish_prototype_guided_checkpoint_v2 import run
import test_prototype_guided_checkpoint as guide_controls


class SelectedCheckpointGuards(unittest.TestCase):
    def rejected(self, error, *, checkpoint_matches=True, source_bound=True):
        with tempfile.TemporaryDirectory() as temp:
            source,guides,phase,output=guide_controls.GuidedCheckpointGuards().fixture(Path(temp))
            source_db=source/'route.odb';source_db.write_bytes(b'completed route')
            local=guides/'local_unrouted.odb';local.write_bytes(b'selected wires cleared')
            path=guides/'assessment.json';g=json.loads(path.read_text())
            g.update(checkpoint_database=str(local) if checkpoint_matches else str(source_db),
                source_database=str(source_db),all_instances_and_nonselected_wires_unchanged=True)
            if source_bound:g['input_sha256'][str(source_db)]=sha(source_db)
            g['artifacts'][str(local)]=sha(local);path.write_text(json.dumps(g))
            with patch('finish_prototype_guided_checkpoint_v2.execute') as native:
                with self.assertRaisesRegex((ValueError,TimeoutError),error):run(source,guides,phase,output)
                native.assert_not_called()
            self.assertFalse(output.exists())

    def test_arbitrary_checkpoint_path_is_rejected(self):
        self.rejected('checkpoint provenance',checkpoint_matches=False)

    def test_completed_source_database_must_be_bound(self):
        self.rejected('guide receipt',source_bound=False)

    def test_selected_repair_retains_original_deadline(self):
        self.rejected('original checkpoint deadline expired')


if __name__=='__main__':unittest.main()
