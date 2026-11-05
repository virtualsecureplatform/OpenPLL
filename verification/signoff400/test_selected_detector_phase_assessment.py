import tempfile,unittest
from pathlib import Path
from assess_selected_detector_phase_probe import read_selected,transitions

class DetectorPhaseAssessmentTests(unittest.TestCase):
    def test_complete_waveform_and_interpolated_physical_edges(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw'
            p.write_text('No. Variables: 2\nNo. Points: 3\nVariables:\n0 TIME time\n1 V(n) voltage\nValues:\n0 0\n0\n1 1e-9\n1.8\n2 2e-9\n0\n')
            rows=read_selected(p,{'signal':'n'},2e-9)
            self.assertEqual(transitions(rows,1),dict(rising_ns=[.5],falling_ns=[1.5000000000000002]))
            with self.assertRaises(ValueError):read_selected(p,{'signal':'n'},3e-9)
    def test_nonfinite_unsaved_variable_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw'
            p.write_text('No. Variables: 3\nNo. Points: 2\nVariables:\n0 TIME time\n1 V(n) voltage\n2 V(other) voltage\nValues:\n0 0\n0\nnan\n1 1e-9\n1.8\n0\n')
            with self.assertRaises(ValueError):read_selected(p,{'signal':'n'},1e-9)

if __name__=='__main__':unittest.main()
