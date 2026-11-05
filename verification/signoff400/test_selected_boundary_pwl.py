import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class PWLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.binary=Path(cls.tmp.name)/'extract'
        subprocess.run(['g++','-O2','-std=c++17',ROOT/'tools/xyce_waveform/extract_boundary_pwl.cpp','-o',cls.binary],check=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def fixture(self,indices='1\n',value='1.8'):
        temp=tempfile.TemporaryDirectory();p=Path(temp.name)
        (p/'raw').write_text(f'No. Variables: 2\nNo. Points: 2\nVariables:\n0 TIME time\n1 V(n) voltage\nValues:\n0 0\n0\n1 2.6e-7\n{value}\n');(p/'indices').write_text(indices)
        return temp,p
    def test_exact_saved_values_written(self):
        temp,p=self.fixture()
        with temp:
            subprocess.run([self.binary,p/'raw',p/'indices',p],check=True,capture_output=True)
            rows=[list(map(float,l.split())) for l in (p/'boundary_0.pwl').read_text().splitlines()]
            self.assertEqual(rows,[[0,0],[260e-9,1.8]])
    def test_duplicate_boundary_column_rejected(self):
        temp,p=self.fixture('1\n1\n')
        with temp:self.assertNotEqual(subprocess.run([self.binary,p/'raw',p/'indices',p],capture_output=True).returncode,0)
    def test_nonfinite_boundary_rejected(self):
        temp,p=self.fixture(value='nan')
        with temp:self.assertNotEqual(subprocess.run([self.binary,p/'raw',p/'indices',p],capture_output=True).returncode,0)
if __name__=='__main__':unittest.main()
