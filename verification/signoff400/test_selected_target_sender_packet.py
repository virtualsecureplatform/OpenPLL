import unittest
from follow_selected_target_sender_packet import ready


class ReadinessTests(unittest.TestCase):
    def test_both_normal_completion_variants_accepted(self):
        for status in ['calibration_waveform_assessed','calibration_waveform_and_supply_power_assessed']:
            self.assertTrue(ready('native_startup_completed_waveform_assessment_pending',status,True))

    def test_live_partial_or_failed_native_never_ready(self):
        for status in [None,'native_startup_running','stopped_without_qualification']:
            self.assertFalse(ready(status,'calibration_waveform_assessed',True))

    def test_missing_assessment_or_provenance_never_ready(self):
        self.assertFalse(ready('native_startup_completed_waveform_assessment_pending',None,True))
        self.assertFalse(ready('native_startup_completed_waveform_assessment_pending','calibration_waveform_assessed',False))


if __name__=='__main__':unittest.main()
