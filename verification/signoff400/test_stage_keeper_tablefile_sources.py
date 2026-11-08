import unittest,tempfile,json,tarfile
from pathlib import Path
from common_v3 import sha,save
from stage_keeper_tablefile_sources import archive_sources
class Archive(unittest.TestCase):
    def fixture(self,root):
        p=root/'sources';p.mkdir();(p/'tables').mkdir();(p/'external_sources.spice').write_text('B0 A 0 V={TABLEFILE("local")}\n');(p/'tables/0.dat').write_text('0 1.8\n1 1.8\n')
        r=p/'assessment.json';save(r,dict(artifacts={str(q):sha(q) for q in [p/'external_sources.spice',p/'tables/0.dat']}));return r
    def test_archive_exact_contents_and_deterministic_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r=self.fixture(root);a=root/'a.tar';b=root/'b.tar';result=archive_sources(r,a);archive_sources(r,b)
            self.assertEqual(sha(a),sha(b));self.assertTrue(result['all_source_archive_members_hash_verified'])
            with tarfile.open(a) as t:self.assertEqual(t.extractfile('tables/0.dat').read(),b'0 1.8\n1 1.8\n')
    def test_tampered_or_uninventoried_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r=self.fixture(root);(r.parent/'extra').write_text('unexpected')
            with self.assertRaisesRegex(ValueError,'inventory'):archive_sources(r,root/'bad.tar')
            (r.parent/'extra').unlink();(r.parent/'tables/0.dat').write_text('changed')
            with self.assertRaisesRegex(ValueError,'Input changed'):archive_sources(r,root/'bad2.tar')
if __name__=='__main__':unittest.main()
