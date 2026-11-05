import tempfile
import unittest
from pathlib import Path
from characterize_coupled_bbpd import capture_metrics, coupled_deck, read_coupled_rows


def rows():
    result = []
    for i in range(901):
        t = i * .1e-9
        q = 1.8 if 15e-9 <= t < 55e-9 else 0.
        result.append([i, t, 0., 0., 0., 0., q, 0.])
    return result


class CoupledBBPD(unittest.TestCase):
    def test_two_events_of_correct_polarity(self):
        self.assertTrue(capture_metrics(rows(), 1.8, 200)['direction_and_two_event_capture_pass'])
        self.assertFalse(capture_metrics(rows(), 1.8, -200)['direction_and_two_event_capture_pass'])

    def test_wrong_double_capture_and_missing_second_event_rejected(self):
        data = rows()
        for r in data:
            r[7] = r[6]
        self.assertFalse(capture_metrics(data, 1.8, 200)['direction_and_two_event_capture_pass'])
        data = rows()
        for r in data:
            if r[1] >= 55e-9:
                r[6] = 1.8
        self.assertFalse(capture_metrics(data, 1.8, 200)['direction_and_two_event_capture_pass'])

    def test_glitch_and_bad_reset_initial_state_rejected(self):
        data = rows()
        for r in data:
            if 35e-9 <= r[1] < 36e-9:
                r[6] = 0.
        self.assertFalse(capture_metrics(data, 1.8, 200)['direction_and_two_event_capture_pass'])
        data = rows()
        for r in data:
            if r[1] < 8e-9:
                r[6] = 1.8
        self.assertFalse(capture_metrics(data, 1.8, 200)['direction_and_two_event_capture_pass'])

    def test_deck_retains_real_pvt_and_replaces_lumped_load(self):
        text = coupled_deck(Path('/pdk'), Path('/model'), Path('/fixture'), 'sf', 1.95, -40, -200, 200)
        self.assertIn('sky130.lib.spice" sf', text)
        self.assertIn('.options device temp=-40', text)
        self.assertIn('9.8n 200p 200p', text)
        self.assertIn('Xreceiver ', text)
        self.assertIn('precision=16', text)
        self.assertNotIn('CUP ', text)
        self.assertNotIn('CDN ', text)

    def test_native_waveform_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'wave.prn'
            for body in ('0 0 0 0 0 0 0 0\n', '0 0 0 0 0 0 0 nan\n',
                         '0 0 0 0 0 0 0 0\n1 0 0 0 0 0 0 0\n'):
                path.write_text('Index TIME\n' + body + 'End of Xyce(TM) Simulation\n')
                with self.assertRaises(RuntimeError):
                    read_coupled_rows(path)


if __name__ == '__main__':
    unittest.main()
