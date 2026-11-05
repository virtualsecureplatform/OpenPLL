import subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
class ExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'extract'
        subprocess.run(['g++','-O2','-std=c++17',ROOT/'tools/xyce_waveform/extract_selected.cpp','-o',cls.binary],check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def check(self,points=2,value='1.8',end='2.6e-7'):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);raw=p/'test.raw'
            raw.write_text(f'Flags: real\nNo. Variables: 2\nNo. Points: {points}\nVariables:\n0 TIME time\n1 V(PLLOUT) voltage\nValues:\n0 0\n0\n1 {end}\n{value}\n')
            return subprocess.run([self.binary,raw,p/'signals.csv'],capture_output=True).returncode
    def test_complete_finite_trace(self):self.assertEqual(self.check(),0)
    def test_truncated_sample_inventory(self):self.assertNotEqual(self.check(points=3),0)
    def test_nonfinite_voltage(self):self.assertNotEqual(self.check(value='nan'),0)
    def test_incomplete_endpoint(self):self.assertNotEqual(self.check(end='2.5e-7'),0)

if __name__=='__main__':unittest.main()
