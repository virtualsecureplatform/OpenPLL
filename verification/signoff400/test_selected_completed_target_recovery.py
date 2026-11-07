import unittest
from recover_selected_completed_target import require_completed


class RecoveryGuards(unittest.TestCase):
    def setUp(self):
        self.args=[dict(state='stopped_without_qualification',reason="FileNotFoundError(2, 'No such file or directory')"),dict(state='native_startup_completed_waveform_assessment_pending'),dict(end_ns=260,samples=45530),dict(analog_cache_key_unchanged=True,measured_points_retained=5)]

    def test_completed(self):require_completed(*self.args)

    def test_partial_native_rejected(self):
        self.args[1]['state']='running_loaded_startup_260ns'
        with self.assertRaises(ValueError):require_completed(*self.args)

    def test_other_failure_rejected(self):
        self.args[0]['reason']='native failed'
        with self.assertRaises(ValueError):require_completed(*self.args)

    def test_lost_point_rejected(self):
        self.args[3]['measured_points_retained']=4
        with self.assertRaises(ValueError):require_completed(*self.args)


if __name__=='__main__':unittest.main()
