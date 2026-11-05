import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from resources import identity, lease


class ResourceControls(unittest.TestCase):
    def test_reservation_release_and_dead_process_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory/'leases.json').write_text(json.dumps({'stale':dict(pid=os.getpid(),birth='wrong')}))
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+2
            with lease(1, .01, deadline, directory=directory, reserve_gib=0) as token:
                entries=json.loads((directory/'leases.json').read_text())
                self.assertEqual(set(entries), {token})
                self.assertEqual(entries[token]['birth'],identity(os.getpid()))
            self.assertEqual(json.loads((directory/'leases.json').read_text()), {})

    def test_overcommit_deadline_and_exception_release(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+2
            with self.assertRaises(RuntimeError):
                with lease(1,.01,deadline,directory=directory,cpu_limit=1,reserve_gib=0):
                    with self.assertRaises(TimeoutError):
                        with lease(1,.01,time.clock_gettime(time.CLOCK_BOOTTIME)+.05,
                                   directory=directory,cpu_limit=1,reserve_gib=0):
                            self.fail('overcommitted')
                    raise RuntimeError('job failed')
            self.assertEqual(json.loads((directory/'leases.json').read_text()),{})
            with self.assertRaises(ValueError):
                with lease(33,1,deadline,directory=directory): self.fail('overcommitted')


if __name__=='__main__': unittest.main()
