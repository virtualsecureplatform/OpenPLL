"""Terminal mapping and streaming voltage scan controls, including invalid data."""
import subprocess,tempfile,unittest
from pathlib import Path
from common_v3 import ROOT
from prepare_prototype_analog_reference import subcircuits
from selected_native_mos_terminals import mos_cards,plan


class TerminalMapping(unittest.TestCase):
    def fixture(self,extra=''):
        return subcircuits('''
.subckt top d g s b
X1 d g s b sky130_fd_pr__nfet_01v8 w=1 l=0.15
X2 d g s b sky130_fd_pr__nfet_01v8 w=1 l=0.15
XR d s __openpll_xyce_poly_resistor w=1 l=1
XD b d __openpll_xyce_pw2nd area=1 perim=1
.ends top
.subckt __openpll_xyce_poly_resistor p n w=1 l=1
R1 p n {l/w}
.ends
.subckt __openpll_xyce_pw2nd p n area=0 perim=0
D1 p n diode area={area}
'''+extra+'''.ends
''')
    def test_parameterized_non_mos_wrappers_and_multiplicity(self):
        p=plan(mos_cards(self.fixture(),'top'),'top',['time','v(d)','v(g)','v(s)','v(b)'])
        self.assertEqual(p['expanded_MOS'],2);self.assertEqual(p['unique_MOS_cards'],1)
        self.assertEqual(p['records'][0]['indices'],[1,2,3,4])
    def test_mos_hidden_in_excluded_wrapper_rejected(self):
        with self.assertRaises(ValueError):mos_cards(self.fixture('Xhidden p p n n sky130_fd_pr__nfet_01v8 w=1 l=.15\n'),'top')
    def test_missing_terminal_rejected(self):
        with self.assertRaises(ValueError):plan(mos_cards(self.fixture(),'top'),'top',['time','v(d)','v(g)','v(s)'])
    def test_ambiguous_terminal_rejected(self):
        with self.assertRaises(ValueError):plan(mos_cards(self.fixture(),'top'),'top',['time','v(d)','v(g)','v(s)','v(b)','v(xpll:g)'])


class StreamingScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.binary=Path(cls.tmp.name)/'scan'
        subprocess.run(['g++','-std=c++17','-O2',str(ROOT/'tools/xyce_waveform/measure_mos_extents.cpp'),'-o',str(cls.binary)],check=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def run_scan(self,raw=None,mapping=None):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);r=d/'raw';m=d/'map'
            r.write_text(raw or 'No. Variables: 5\nNo. Points: 2\nValues:\n0 0\n1.8\n1.8\n0\n0\n1 2.6e-7\n-.02\n0\n0\n0\n')
            m.write_text(mapping or '1 5 2 1\n0 1 2 3 4 2\n')
            return subprocess.run([str(self.binary),str(r),str(m)],capture_output=True,text=True,timeout=20)
    def test_signed_extrema_and_full_coverage(self):
        r=self.run_scan();self.assertEqual(r.returncode,0)
        row=next(x.split('\t')for x in r.stdout.splitlines()if x.startswith('EXT\t0\tDS'))
        self.assertAlmostEqual(float(row[3]),-.02);self.assertAlmostEqual(float(row[4]),1.8)
        self.assertIn('COMPLETE\t2\t5\t2\t1\t',r.stdout)
    def test_partial_sample_rejected(self):
        self.assertNotEqual(self.run_scan(raw='No. Variables: 5\nNo. Points: 2\nValues:\n0 0\n1\n0\n0\n0\n1 2.6e-7\n1\n').returncode,0)
    def test_nonfinite_rejected(self):
        self.assertNotEqual(self.run_scan(raw='No. Variables: 5\nNo. Points: 2\nValues:\n0 0\nnan\n0\n0\n0\n').returncode,0)
    def test_partial_map_row_rejected(self):self.assertNotEqual(self.run_scan(mapping='1 5 2 1\n0 1 2 3 4 2\n0 1\n').returncode,0)
    def test_time_column_as_voltage_rejected(self):self.assertNotEqual(self.run_scan(mapping='1 5 2 1\n0 0 2 3 4 2\n').returncode,0)
    def test_wrong_declared_count_rejected(self):
        self.assertNotEqual(self.run_scan(raw='No. Variables: 5\nNo. Points: 3\nValues:\n0 0\n1\n0\n0\n0\n1 2.6e-7\n1\n0\n0\n0\n').returncode,0)


if __name__=='__main__':unittest.main()
