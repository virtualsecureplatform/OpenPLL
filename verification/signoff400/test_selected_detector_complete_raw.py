import tempfile,unittest
from pathlib import Path
from assess_selected_detector_phase_probe_v3 import read_selected,transitions


class CompletedRawTest(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.raw=Path(self.temp.name)/'wave.raw'
    def tearDown(self):self.temp.cleanup()
    def write(self,count,tail='1.8\n0\n'):
        self.raw.write_text(f'No. Variables: 3\nNo. Points: {count}\nVariables:\n0 TIME time\n1 V(A) voltage\n2 V(B) voltage\nValues:\n0 0\n0\n0\n1 1e-8\n.5\n0\n2 1e-8\n1.2\n0\n3 8e-8\n'+tail)

    def test_all_declared_samples_at_rounded_time_collisions_are_retained(self):
        self.write(4);rows=read_selected(self.raw,{'a':'A'},80e-9)
        self.assertEqual(len(rows),4);self.assertEqual(rows[1][0],rows[2][0])
        self.assertEqual(transitions(rows,1)['rising_ns'],[10])

    def test_incomplete_declared_native_output_is_rejected(self):
        self.write(5)
        with self.assertRaisesRegex(ValueError,'every declared sample'):read_selected(self.raw,{'a':'A'},80e-9)
        self.write(4,'1.8\n')
        with self.assertRaisesRegex(ValueError,'every declared sample'):read_selected(self.raw,{'a':'A'},80e-9)

    def test_nonfinite_unsaved_role_is_not_silently_ignored(self):
        self.write(4,'1.8\nnan\n')
        with self.assertRaisesRegex(ValueError,'nonfinite'):read_selected(self.raw,{'a':'A'},80e-9)


if __name__=='__main__':unittest.main()
