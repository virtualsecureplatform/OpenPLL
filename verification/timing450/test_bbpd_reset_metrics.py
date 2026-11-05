import unittest
from bbpd_reset_metrics import startup_metrics


def waveform(release):
    rows = []
    for i in range(901):
        t = i * .1e-9
        clocks = (15e-9 <= t < 35e-9 or 55e-9 <= t < 75e-9) if release == 1 else 55e-9 <= t < 75e-9
        toggle = 15e-9 <= t < 55e-9 if release == 1 else t >= 55e-9
        rows.append([i,t,0,0,0,1.8 if clocks else 0,1.8 if toggle else 0,0])
    return rows


class BBPDStartup(unittest.TestCase):
    def test_early_and_late_reset_release(self):
        for release in (1,15,25,35):
            self.assertTrue(startup_metrics(waveform(release),1.8,200,release)['startup_inhibit_capture_pass'])

    def test_early_event_after_late_release_rejected(self):
        self.assertFalse(startup_metrics(waveform(1),1.8,200,25)['startup_inhibit_capture_pass'])

    def test_missing_event_wrong_direction_and_clock_glitch_rejected(self):
        rows = waveform(25)
        self.assertFalse(startup_metrics(rows,1.8,-200,25)['startup_inhibit_capture_pass'])
        for r in rows:
            r[6] = 0
        self.assertFalse(startup_metrics(rows,1.8,200,25)['startup_inhibit_capture_pass'])
        rows = waveform(25)
        for r in rows:
            if 20e-9 <= r[1] <= 21e-9:
                r[5] = 1.8
        self.assertFalse(startup_metrics(rows,1.8,200,25)['startup_inhibit_capture_pass'])

    def test_unobserved_or_unknown_scenarios_rejected(self):
        with self.assertRaises(RuntimeError):
            startup_metrics(waveform(1),1.8,200,10)
        with self.assertRaises(RuntimeError):
            startup_metrics(waveform(1)[500:],1.8,200,1)


if __name__ == '__main__':
    unittest.main()
