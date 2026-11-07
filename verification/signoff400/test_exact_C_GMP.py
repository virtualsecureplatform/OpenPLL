import json,subprocess,tempfile,unittest
from pathlib import Path

class ExactGMP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.folder=Path(cls.tmp.name);cls.binary=cls.folder/'ldl'
        src=Path(__file__).resolve().parents[2]/'tools/capacitance_energy/exact_sparse_ldl.cpp'
        subprocess.run(['g++','-std=c++20','-O2',str(src),'-lgmpxx','-lgmp','-o',str(cls.binary)],check=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def run_case(self,edges,seconds='5'):
        src=self.folder/'edges';out=self.folder/'report';src.write_text(edges)
        subprocess.run([str(self.binary),str(src),str(out),seconds],check=True)
        return json.loads(out.read_text())
    def test_singular_passive(self):self.assertTrue(self.run_case('2 1\n0 1 2\n')['passivity_certified'])
    def test_higher_order_negative_mode(self):
        r=self.run_case('3 6\n0 1 2\n1 2 2\n0 2 2\n0 -1 -1\n1 -1 -1\n2 -1 -1\n')
        self.assertTrue(r['indefiniteness_proved'])
    def test_zero_diagonal_off_diagonal(self):self.assertTrue(self.run_case('2 2\n0 1 1\n0 -1 -1\n')['indefiniteness_proved'])
    def test_bound_is_inconclusive(self):
        r=self.run_case('2 1\n0 1 1\n','-1');self.assertEqual(r['state'],'time_bound_inconclusive');self.assertFalse(r['passivity_certified'])
    def test_fractional_coefficients(self):self.assertTrue(self.run_case('2 2\n0 1 1/1000000000000000\n0 -1 1/3000000000000000\n')['passivity_certified'])

if __name__=='__main__':unittest.main()
