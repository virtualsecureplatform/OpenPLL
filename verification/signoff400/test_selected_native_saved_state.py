import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from run_selected_dco_saved_state_control import shifted


class SavedStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.binary=Path(cls.tmp.name)/'extract'
        source=Path(__file__).resolve().parents[2]/'tools/xyce_waveform/extract_saved_state_v2.cpp'
        subprocess.run(['g++','-O2','-std=c++17',source,'-o',cls.binary],check=True)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def raw(self, label='TIME', value='1.4', last='1.75001e-7'):
        return (f'No. Variables: 2\nNo. Points: 3\nVariables:\n0 {label} time\n1 V(node) voltage\nValues:\n'
                f'0 0\n0\n\n1 1.74999e-7\n0.3\n\n2 {last}\n{value}\n')

    def extract(self, text):
        with tempfile.TemporaryDirectory()as tmp:
            p=Path(tmp);(p/'source.raw').write_text(text)
            r=subprocess.run([self.binary,p/'source.raw','1.75e-7',p/'state.json'],capture_output=True,text=True)
            return r,json.loads((p/'state.json').read_text())if (p/'state.json').exists()else None

    def test_actual_knot_retained_without_interpolation(self):
        for label in ('TIME','time'):
            result,state=self.extract(self.raw(label))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(state['time_s'],1.75001e-7)
            self.assertEqual(state['values'],[1.75001e-7,1.4])

    def test_nonfinite_incomplete_and_distant_state_rejected(self):
        for raw in (self.raw(value='nan'),self.raw().replace('1.4\n',''),self.raw(last='1.76e-7')):
            with self.subTest(raw=raw):
                result,state=self.extract(raw)
                self.assertNotEqual(result.returncode,0)
                self.assertIsNone(state)

    def test_history_shift_preserves_time_and_linear_start_voltage(self):
        self.assertEqual(shifted([(0,0),(1,1),(3,3)],2),[(0,2),(1,3)])
        self.assertEqual(shifted([(0,0),(1,1),(3,3)],1),[(0,1),(2,3)])
        with self.assertRaises(ValueError):shifted([(0,0),(1,1)],2)


if __name__=='__main__':unittest.main()
