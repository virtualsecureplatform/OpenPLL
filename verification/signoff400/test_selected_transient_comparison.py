import tempfile,unittest
from pathlib import Path
from compare_selected_transient import compare

class TransientTests(unittest.TestCase):
    def test_linear_reference_and_candidate_agree(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'ref.csv').write_text('time,v(pllout)\n0,0\n5e-10,.5\n1e-9,1\n')
            (p/'raw').write_text('Flags: real\nNo. Variables: 2\nNo. Points: 2\nVariables:\n0 TIME time\n1 V(PLLOUT) voltage\nValues:\n0 0\n0\n1 1e-9\n1\n')
            r=compare(p/'ref.csv',p/'raw',1e-9);self.assertTrue(r['within_diagnostic_voltage_tolerance']);self.assertFalse(r['release_ready'])
            with self.assertRaises(ValueError):compare(p/'ref.csv',p/'raw',2e-9)

if __name__=='__main__':unittest.main()
