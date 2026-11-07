import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from reconnect_selected_corner_observers import parent_ready


class ParentInitialization(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.parent=root/'parent';self.guard=root/'guard';self.guard.mkdir()
        (self.guard/'owner.json').write_text(json.dumps(dict(pid=123,birth='1')))

    def test_missing_parent_waits_on_live_guard(self):
        with patch('reconnect_selected_corner_observers.identity',return_value='1'):
            self.assertFalse(parent_ready(self.parent,self.guard))

    def test_dead_guard_rejected(self):
        with patch('reconnect_selected_corner_observers.identity',return_value=None):
            with self.assertRaises(RuntimeError):parent_ready(self.parent,self.guard)

    def test_stopped_parent_rejected(self):
        self.parent.mkdir();(self.parent/'owner.json').write_text(json.dumps(dict(pid=123,birth='1')))
        (self.parent/'status.json').write_text(json.dumps(dict(state='stopped_without_qualification')))
        with self.assertRaises(RuntimeError):parent_ready(self.parent,self.guard)

    def test_ready_live_parent(self):
        self.parent.mkdir();(self.parent/'owner.json').write_text(json.dumps(dict(pid=123,birth='1')))
        (self.parent/'status.json').write_text(json.dumps(dict(state='waiting_for_full_native_slot')))
        with patch('reconnect_selected_corner_observers.identity',return_value='1'):
            self.assertTrue(parent_ready(self.parent,self.guard))


if __name__=='__main__':unittest.main()
