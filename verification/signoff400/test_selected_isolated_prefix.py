import tempfile,unittest
from pathlib import Path
from assess_selected_isolated_control import prefix

class IsolatedPrefixTests(unittest.TestCase):
    def test_budget_prefix_discards_incomplete_last_sample(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw';p.write_text('No. Variables: 2\nNo. Points: \nVariables:\n0 TIME time\n1 V(PLLOUT) voltage\nValues:\n0 0\n0\n1 1e-9\n1.8\n2 2e-9\n1.8e')
            rows,info=prefix(p);self.assertEqual(len(rows),2)
            self.assertTrue(info['incomplete_final_sample_discarded']);self.assertFalse(info['declared_sample_count_complete'])
    def test_nonfinite_complete_sample_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw';p.write_text('No. Variables: 2\nNo. Points: \nVariables:\n0 TIME time\n1 V(PLLOUT) voltage\nValues:\n0 0\nnan\n')
            with self.assertRaises(ValueError):prefix(p)

if __name__=='__main__':unittest.main()
