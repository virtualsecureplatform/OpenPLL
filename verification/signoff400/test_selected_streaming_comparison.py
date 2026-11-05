import tempfile,unittest
from pathlib import Path
from compare_selected_streaming import compare


class StreamingComparisonTests(unittest.TestCase):
    def test_exact_ramp_and_missing_endpoint(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=p/'ref.csv';c=p/'candidate.csv'
            r.write_text('time_s,v(pllout)\n0,0\n1e-12,0.5\n2e-12,1\n')
            c.write_text('time_s,v(PLLOUT)\n1e-13,0.05\n1e-12,0.5\n2e-12,1\n')
            report=compare(r,c,2e-12)
            self.assertLess(report['maximum_voltage_difference_V'],1e-15)
            self.assertFalse(report['DC_comparison']);self.assertFalse(report['release_ready'])
            with self.assertRaises(ValueError):compare(r,c,3e-12)

    def test_rejects_nonfinite_and_late_bootstrap(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=p/'ref.csv';c=p/'candidate.csv'
            r.write_text('time_s,v(pllout)\n0,0\n3e-12,1\n')
            for samples in ('2e-12,0\n3e-12,1\n','1e-13,nan\n3e-12,1\n'):
                c.write_text('time_s,v(pllout)\n'+samples)
                with self.assertRaises(ValueError):compare(r,c,3e-12)


if __name__=='__main__':unittest.main()
