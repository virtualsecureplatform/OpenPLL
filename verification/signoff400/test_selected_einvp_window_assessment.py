import tempfile,unittest
from pathlib import Path
from assess_selected_einvp_window_replay import read,compare


class WindowTests(unittest.TestCase):
    def test_interpolation_and_measured_error(self):
        reference=[[0.,0.],[5e-9,1.],[10e-9,0.]]
        observed=[[0.,0.],[2.5e-9,.6],[5e-9,1.1],[7.5e-9,.6],[10e-9,.1]]
        a=compare(reference,observed,1,1,2.5e-9)
        self.assertEqual(a['compared_samples'],4)
        self.assertAlmostEqual(a['maximum_absolute_error_V'],.1)
        self.assertAlmostEqual(a['RMS_error_V'],.1)

    def test_partial_and_nonfinite_streams_rejected(self):
        with tempfile.TemporaryDirectory()as folder:
            p=Path(folder)/'x.csv'
            for text in ['TIME,V(x)\n0,0\n5e-9,1\n','TIME,V(x)\n0,0\n1e-8,nan\n','TIME,V(x)\n0,0\n0,1\n1e-8,1\n']:
                p.write_text(text)
                with self.assertRaises(ValueError):read(p)

    def test_complete_xyce_footer(self):
        with tempfile.TemporaryDirectory()as folder:
            p=Path(folder)/'x.csv';p.write_text('TIME,V(x)\n0,0\n1e-8,1\nEnd of Xyce(TM) Simulation\n')
            _,rows=read(p);self.assertEqual(len(rows),2)


if __name__=='__main__':unittest.main()
