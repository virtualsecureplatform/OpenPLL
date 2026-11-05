from pathlib import Path
import tempfile
import unittest
from run_prototype_capture_refinement import table


class RefinementWaveformIntegrity(unittest.TestCase):
    def test_explicit_q_data_and_control_column_identity_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'wave.dat';good='time v(clk) v(q0) v(d0) v(ctrl0)\n0 0 0 0 0\n3e-8 0 1.8 1.8 1.8\n'
            p.write_text(good);self.assertEqual(len(table(p,1)),2)
            for bad in (good.replace('v(q0) v(d0)','v(d0) v(q0)'),good.replace('3e-8','2e-8'),good.replace('1.8 1.8 1.8','1.8 nan 1.8')):
                p.write_text(bad)
                with self.assertRaises(ValueError):table(p,1)


if __name__=='__main__':unittest.main()
