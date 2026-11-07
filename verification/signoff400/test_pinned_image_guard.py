import os,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from pinned_image_guard import ImageGuard

class Guard(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.image=Path(self.temp.name)/'image.sif';self.other=Path(self.temp.name)/'rtl.v';self.image.write_bytes(b'original');self.other.write_bytes(b'RTL');self.pins={str(p):sha(p)for p in [self.image,self.other]};self.guard=ImageGuard(self.image)
    def test_unchanged_image_cached_and_final_fully_checked(self):
        self.guard.check(self.pins);self.guard.check(self.pins);self.assertEqual((self.guard.hash_checks,self.guard.metadata_hits),(1,1));self.guard.check(self.pins,full=True);self.assertEqual(self.guard.hash_checks,2)
    def test_same_size_write_and_restored_mtime_rejected(self):
        self.guard.check(self.pins);s=self.image.stat();self.image.write_bytes(b'modified');os.utime(self.image,ns=(s.st_atime_ns,s.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'hash differs'):self.guard.check(self.pins)
    def test_other_pins_never_cached(self):
        self.guard.check(self.pins);self.other.write_bytes(b'BAD')
        with self.assertRaisesRegex(ValueError,'Input changed'):self.guard.check(self.pins)
    def test_replacement_with_identical_content_rehashed(self):
        self.guard.check(self.pins);p=self.image.with_suffix('.new');p.write_bytes(self.image.read_bytes());p.replace(self.image);self.guard.check(self.pins);self.assertEqual(self.guard.hash_checks,2)
    def test_changed_expected_digest_rejected(self):
        self.guard.check(self.pins)
        with self.assertRaisesRegex(ValueError,'hash differs'):self.guard.check({**self.pins,str(self.image):'0'*64})
    def test_missing_image_pin_rejected(self):
        with self.assertRaisesRegex(ValueError,'remain pinned'):self.guard.check({str(self.other):sha(self.other)})
if __name__=='__main__':unittest.main()
