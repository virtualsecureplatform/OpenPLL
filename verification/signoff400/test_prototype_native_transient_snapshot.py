from pathlib import Path
import tempfile
import unittest
from prototype_native_transient_snapshot import read_snapshot


class NativeTransientSnapshot(unittest.TestCase):
    raw = ('Plotname: Transient Analysis\nFlags: real\nNo. Variables: 2\nNo. Points: 3\n'
           'Variables:\n0 time time\n1 v(out) voltage\nValues:\n0 0\n0\n1 1e-9\n1.7\n2 2e-9\n1.8\n')

    def read(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'native.raw'
            path.write_text(text)
            return read_snapshot(path, 2e-9, 1e-9, ['v(out)'])

    def test_complete_last_state_and_window_are_streamed(self):
        result = self.read(self.raw)
        self.assertEqual(result['last_values']['v(out)'], 1.8)
        self.assertEqual(result['tracked_full_interval_ranges']['v(out)'], [0., 1.8])
        self.assertAlmostEqual(result['maximum_trailing_node_voltage_span_v'], 0.1)
        self.assertFalse(result['warm_restart_qualified'])

    def test_rejects_truncation_duplicate_time_and_nonfinite_samples(self):
        for wrong in (self.raw.rsplit('1.8', 1)[0], self.raw.replace('2 2e-9', '2 1e-9'),
                      self.raw.replace('1.8', 'nan'), self.raw + '0 0\n'):
            with self.assertRaises(ValueError):
                self.read(wrong)

    def test_rejects_wrong_scope_vectors_and_missing_end(self):
        for wrong in (self.raw.replace('Flags: real', 'Flags: complex'),
                      self.raw.replace('1 v(out) voltage', '1 time voltage'),
                      self.raw.replace('2 2e-9', '2 1.5e-9')):
            with self.assertRaises(ValueError):
                self.read(wrong)


if __name__ == '__main__':
    unittest.main()
