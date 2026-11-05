import tempfile,unittest
from pathlib import Path
from run_selected_detector_phase_probe import export,first_sample,pulse

class DetectorPhaseProbeTests(unittest.TestCase):
    def test_phase_is_centered_independently_of_ramp_duration(self):
        for ramp in [100,600]:
            numbers=pulse(1,ramp,40)[6:-1].split()
            delay=float(numbers[2][:-1]);rise=float(numbers[3][:-1])/1000
            self.assertAlmostEqual(delay+rise/2,21)
        with self.assertRaises(ValueError):pulse(float('nan'),100,40)
    def test_export_preserves_wrappers_and_only_declared_top_cards(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'source';out=p/'devices'
            source.write_text('.subckt wrapper a b\nRinner a b 1\n.ends\n.subckt IntegerPLL_400MHz_PrototypeTop a b\nXflat0 a b wrapper\nXflat1 a b wrapper\nC0 a b 1f\nC1 a b 2f\n.ends\n')
            export(source,dict(selected_primitives=['Xflat0'],retained_passive_cards=['C0']),out)
            text=out.read_text();self.assertIn('Rinner',text);self.assertIn('Xflat0',text)
            self.assertNotIn('Xflat1',text);self.assertNotIn('C1',text)
    def test_initial_sample_rejects_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw';p.write_text('No. Variables: 2\nVariables:\n0 TIME time\n1 V(n) voltage\nValues:\n0 0\nnan\n')
            with self.assertRaises(ValueError):first_sample(p)

if __name__=='__main__':unittest.main()
