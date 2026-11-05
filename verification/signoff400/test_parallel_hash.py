import hashlib
from pathlib import Path
import tempfile
import unittest

from parallel_hash import sha_prefetch


class HashControls(unittest.TestCase):
    def test_standard_sha256_across_block_boundaries_and_worker_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'data'
            for length in (0,1,63,64,65,1023,1024,1025,2**20+73):
                data=(bytes(range(256))*(length//256+1))[:length];p.write_bytes(data)
                for readers in (1,4,8):
                    self.assertEqual(sha_prefetch(p,readers,1024),hashlib.sha256(data).hexdigest())
            with self.assertRaises(TimeoutError):sha_prefetch(p,deadline=0)
            with self.assertRaises(ValueError):sha_prefetch(p,readers=0)


if __name__=='__main__':unittest.main()
