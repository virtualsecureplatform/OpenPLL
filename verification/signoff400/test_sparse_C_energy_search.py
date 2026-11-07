import json,subprocess,tempfile,unittest
from fractions import Fraction as F
from pathlib import Path

class SparseEnergySearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.folder=Path(cls.tmp.name);cls.binary=cls.folder/'search'
        cpp=Path(__file__).resolve().parents[2]/'tools/capacitance_energy/search_sparse_C_energy.cpp'
        subprocess.run(['g++','-std=c++20','-O3',str(cpp),'-lgmpxx','-lgmp','-o',str(cls.binary)],check=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def candidate(self,n,edges,seconds='5'):
        src=self.folder/'edges';vector=self.folder/'vector';report=self.folder/'report'
        src.write_text(f'{n} {len(edges)}\n'+''.join(f'{a} {b} {c}\n'for a,b,c in edges))
        subprocess.run([str(self.binary),str(src),str(vector),str(report),seconds],check=True)
        values=list(map(int,vector.read_text().split()));self.assertEqual(values[0],n);v=values[1:];self.assertEqual(len(v),n)
        energy=sum(F(c)*(v[a]-(0 if b==-1 else v[b]))**2 for a,b,c in edges)/10**18
        return energy,json.loads(report.read_text())
    def test_higher_order_negative_mode_exactly_verified(self):
        edges=[(0,1,'2f'),(1,2,'2f'),(0,2,'2f'),(0,-1,'-1f'),(1,-1,'-1f'),(2,-1,'-1f')]
        # TSV uses exact fractions, while the expected energy is independently rational.
        edges=[(a,b,str(F(c[:-1])*F(1,10**15)))for a,b,c in edges]
        e,r=self.candidate(3,edges);self.assertLess(e,0);self.assertTrue(r['search_is_not_passivity_certificate'])
    def test_signed_passive_operator_has_nonnegative_exact_energy(self):
        e,_=self.candidate(2,[(0,1,'-2'),(0,-1,'5'),(1,-1,'5')]);self.assertGreaterEqual(e,0)
    def test_ground_only_operator(self):
        e,_=self.candidate(1,[(0,-1,'1/1000000000000000')]);self.assertGreater(e,0)
    def test_time_bound_does_not_claim_passivity(self):
        e,r=self.candidate(2,[(0,1,'2'),(0,-1,'1')],'-1');self.assertTrue(r['time_bound_reached']);self.assertTrue(r['search_is_not_passivity_certificate'])

if __name__=='__main__':unittest.main()
