"""Exercise actual overlapping processes, budgets and fail-closed cleanup."""
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import parallel_geometry_jobs as native
from common import sha


class ParallelGeometry(unittest.TestCase):
    def run_native(self, jobs, output, pins=None, seconds=15):
        with patch.object(native, 'lease', lambda *args: nullcontext()):
            return native.run_jobs(jobs, output, pins or {},
                time.clock_gettime(time.CLOCK_BOOTTIME)+seconds, workers=2)

    def job(self, label, code, *args, **kw):
        return dict(label=label, command=[sys.executable, '-c', code, *map(str, args)], **kw)

    def assert_exited(self, output):
        for path in output.glob('*.process.json'):
            row=json.loads(path.read_text())
            self.assertNotEqual(native.identity(row['pid']), row['birth'])

    def test_jobs_overlap_and_address_limit_is_applied(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            code='''import pathlib,resource,sys,time
p=pathlib.Path(sys.argv[1]);(p/sys.argv[2]).touch()
deadline=time.monotonic()+5
while not all((p/n).exists() for n in ('a.ready','b.ready')):
 if time.monotonic()>deadline:raise SystemExit(9)
 time.sleep(.01)
assert resource.getrlimit(resource.RLIMIT_AS)==(8*1024**3,8*1024**3)
'''
            result=self.run_native([self.job('a',code,out,'a.ready'),self.job('b',code,out,'b.ready')],out)
            self.assertEqual(result,dict(a=0,b=0))
            self.assert_exited(out)

    def test_failure_terminates_a_peer_that_ignores_term(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            peer='import pathlib,signal,sys,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);pathlib.Path(sys.argv[1]).touch();time.sleep(30)'
            fail='''import pathlib,sys,time
deadline=time.monotonic()+5
while not pathlib.Path(sys.argv[1]).exists():
 if time.monotonic()>deadline:raise SystemExit(8)
 time.sleep(.01)
raise SystemExit(3)
'''
            with self.assertRaises(RuntimeError):
                self.run_native([self.job('peer',peer,out/'ready'),self.job('fail',fail,out/'ready')],out)
            self.assert_exited(out)

    def test_whole_deadline_kills_native_process(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            with self.assertRaises(TimeoutError):
                self.run_native([self.job('slow','import time;time.sleep(30)')],out,seconds=.2)
            self.assert_exited(out)

    def test_changed_inputs_cannot_produce_success(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);source=out/'input';source.write_text('before')
            code='import pathlib,sys;pathlib.Path(sys.argv[1]).write_text("after")'
            with self.assertRaises(ValueError):
                self.run_native([self.job('change',code,source)],out,{str(source):sha(source)})
            self.assert_exited(out)

    def test_density_exit_is_evidence_and_duplicate_labels_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            result=self.run_native([self.job('density','raise SystemExit(7)',allow_nonzero=True)],out)
            self.assertEqual(result,dict(density=7))
            with self.assertRaises(ValueError):
                self.run_native([self.job('same','pass'),self.job('same','pass')],out)


if __name__=='__main__':unittest.main()
