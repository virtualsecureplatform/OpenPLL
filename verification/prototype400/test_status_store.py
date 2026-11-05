"""Concurrent phase reporters must preserve each other's status fields."""
import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest
import status_store


def report(root,number):
    status_store.ROOT=Path(root)
    for count in range(25):
        status_store.update_root(f'phase_{number}',dict(sequence=count,observed_utc=str(count)))


class StatusStoreTests(unittest.TestCase):
    def test_concurrent_phase_updates_preserve_all_fields(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'build/timing400/prototype_001/status.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(dict(prototype_handoff_qualified=False)))
            children=[multiprocessing.Process(target=report,args=(root,i)) for i in range(4)]
            for child in children:child.start()
            for child in children:
                child.join(timeout=20)
                if child.is_alive():child.terminate();child.join();self.fail('status writer timed out')
                self.assertEqual(child.exitcode,0)
            value=json.loads(path.read_text())
            self.assertFalse(value['prototype_handoff_qualified'])
            for i in range(4):self.assertEqual(value[f'phase_{i}']['sequence'],24)
            self.assertFalse(path.with_suffix('.json.tmp').exists())


if __name__=='__main__':unittest.main()
