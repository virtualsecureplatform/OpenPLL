"""Native/export reconciliation, repeated lifetimes and malformed traces."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT


def group(gid,resistance='2500'):
    return f'''BEGIN {gid} "NET"
NODE {gid} p "A" 0 0 0 0
BRANCH {gid} p r
EDGE {gid} p p q {resistance} 2 512
NODE {gid} q "B" 1 0 0 0
BRANCH {gid} q r
EDGE {gid} q p q {resistance} 2 512
END {gid}
'''


class NativeRExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.binary=Path(cls.temp.name)/'compare'
        subprocess.run(['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off',
                        str(ROOT/'tools/native_r_export_audit/main.cpp'),'-o',str(cls.binary)],
                       check=True,capture_output=True,timeout=120)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def compare(self,root,native,export=None):
        (root/'native.log').write_text(native)
        (root/'export.ext').write_text(export or '''scale 1000 1 500000
rnode "A" 0 0 0 0 0
rnode "B" 0 0 1 0 0
resist "A" "B" 2.5
''')
        config=dict(native=str(root/'native.log'),export=str(root/'export.ext'),
                    output=str(root/'out'),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+60)
        (root/'config.json').write_text(json.dumps(config))
        result=subprocess.run([self.binary,root/'config.json'],capture_output=True,text=True,timeout=60)
        return result

    def test_value_changes_distinguish_lifetimes_without_selecting_domains(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.compare(root,group(1)+group(2,'3000'))
            self.assertEqual(r.returncode,0,r.stderr)
            summary=json.loads((root/'out/summary.json').read_text())
            self.assertEqual(summary['matching_group_ids_by_label'],{'NET':['1']})
            self.assertEqual(summary['labels_with_one_matching_group'],1)
            self.assertFalse(summary['runtime_model_eligible'])
            rows=[json.loads(r) for r in (root/'out/groups.jsonl').read_text().splitlines()]
            self.assertFalse(rows[1]['printed_resistors_and_incidence_match'])

    def test_equal_lifetimes_remain_ambiguous_and_extra_export_edges_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.compare(root,group(1)+group(2))
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads((root/'out/summary.json').read_text())['labels_with_multiple_matching_groups'],1)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            exported='scale 1000 1 500000\nrnode "A" 0 0 0 0 0\nrnode "B" 0 0 1 0 0\nresist "A" "B" 2.5\nresist "A" "EXTERNAL" 1\n'
            r=self.compare(root,group(1),exported)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads((root/'out/summary.json').read_text())['matching_printed_groups'],0)

    def test_unclosed_unpaired_nonfinite_and_quoted_corruption_fail_closed(self):
        for text in (group(1).replace('END 1\n',''),group(1).replace('BRANCH 1 q r\n',''),
                     group(1,'nan'),group(1).replace('END 1','END 1 "'),
                     group(1).replace('EDGE 1 q p q 2500 2 512','EDGE 1 q p q 3000 2 512')):
            with self.subTest(text=text),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);r=self.compare(root,text)
                self.assertNotEqual(r.returncode,0)
                self.assertFalse((root/'out/summary.json').exists())


if __name__=='__main__':
    unittest.main()
