"""Exercise time-window exclusion and inherit malformed-stream controls."""
import subprocess,tempfile,unittest
from pathlib import Path
from common_v3 import ROOT
import test_selected_mos_voltage_scan as controls


class WindowStreamingScan(controls.StreamingScan):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.binary=Path(cls.tmp.name)/'scan'
        subprocess.run(['g++','-std=c++17','-O2',str(ROOT/'tools/xyce_waveform/measure_mos_extents_v2.cpp'),'-o',str(cls.binary)],check=True)
    def run_scan(self,raw=None,mapping=None,start_ns=0):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);r=d/'raw';m=d/'map'
            r.write_text(raw or 'No. Variables: 5\nNo. Points: 2\nValues:\n0 0\n1.8\n1.8\n0\n0\n1 2.6e-7\n-.02\n0\n0\n0\n')
            m.write_text(mapping or '1 5 2 1\n0 1 2 3 4 2\n')
            return subprocess.run([str(self.binary),str(r),str(m),str(start_ns)],capture_output=True,text=True,timeout=20)
    def test_early_peak_excluded(self):
        r=self.run_scan(start_ns=200);self.assertEqual(r.returncode,0)
        row=next(x.split('\t')for x in r.stdout.splitlines()if x.startswith('EXT\t0\tDS'))
        self.assertAlmostEqual(float(row[3]),-.02);self.assertAlmostEqual(float(row[4]),-.02)
        self.assertIn('WINDOW\t200\t1\t',r.stdout)
    def test_negative_window_rejected(self):self.assertNotEqual(self.run_scan(start_ns=-1).returncode,0)
    def test_window_at_end_rejected(self):self.assertNotEqual(self.run_scan(start_ns=260).returncode,0)


if __name__=='__main__':unittest.main()
