import copy,json,tempfile,unittest
from pathlib import Path
from run_selected_mixed_signal import measured_point

class MeasuredPointTests(unittest.TestCase):
    def point(self,change=None):
        d=dict(signals={'v(pllout)':dict(rising_edges_200_260ns=23,mean_frequency_mhz=392.31)},coarse_code=dict(window_codes=[20]),dco_code=dict(window_codes=[111]))
        if change:change(d)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'point.json';p.write_text(json.dumps(d));return measured_point(p)
    def test_measured_frequency_units(self):
        self.assertEqual(self.point(),(20,111,392310000000))
    def test_reject_tuning_changes_during_measurement(self):
        with self.assertRaises(ValueError):self.point(lambda d:d['dco_code'].update(window_codes=[111,112]))
    def test_reject_missing_cycles(self):
        with self.assertRaises(ValueError):self.point(lambda d:d['signals']['v(pllout)'].update(rising_edges_200_260ns=1))
    def test_reject_nonfinite_frequency(self):
        with self.assertRaises(ValueError):self.point(lambda d:d['signals']['v(pllout)'].update(mean_frequency_mhz=float('nan')))
    def test_reject_unsafe_fine_code(self):
        with self.assertRaises(ValueError):self.point(lambda d:d['dco_code'].update(window_codes=[255]))

if __name__=='__main__':unittest.main()

class RunnerExitTests(unittest.TestCase):
    def test_missing_calibration_has_distinct_exit(self):
        from run_selected_mixed_signal import exit_status
        self.assertEqual(exit_status(dict(state='needs_native_tuning_points')),3)
    def test_failed_case_cannot_return_success(self):
        from run_selected_mixed_signal import exit_status
        self.assertEqual(exit_status(dict(state='diagnostic_failed',native_exit=0)),1)
    def test_only_complete_functional_pass_returns_zero(self):
        from run_selected_mixed_signal import exit_status
        r=dict(state='diagnostic_simulation_completed',functional_trace_pass=True,native_exit=0,terminal_marker_present=True)
        self.assertEqual(exit_status(r),0);r['terminal_marker_present']=False;self.assertEqual(exit_status(r),1)
