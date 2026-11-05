import tempfile,unittest
from pathlib import Path
from capture_selected_native_initial_snapshot import fingerprint
from audit_selected_dco_final_bias import last_sample

class DCOFinalBiasTests(unittest.TestCase):
    def fixture(self,p):
        p.write_text('No. Variables: 3\nNo. Points: 2\nVariables:\n0 TIME time\n1 V(a) voltage\n2 V(b) voltage\nValues:\n0 0\n0\n1.8\n1 2.6e-7\n1.8\n0\n')
    def test_reads_only_complete_final_sample(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw';self.fixture(p)
            names,values=last_sample(p,fingerprint(p))
            self.assertEqual(names,['TIME','V(a)','V(b)']);self.assertEqual(values,[260e-9,1.8,0])
    def test_rejects_changed_or_truncated_raw(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw';self.fixture(p);before=fingerprint(p)
            p.write_text(p.read_text()[:-2])
            with self.assertRaises(ValueError):last_sample(p,before)
            with self.assertRaises(ValueError):last_sample(p,fingerprint(p))

if __name__=='__main__':unittest.main()
