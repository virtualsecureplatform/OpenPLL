import tempfile,unittest
from pathlib import Path
from assess_selected_interface_observations import assess


class ObservationTests(unittest.TestCase):
    def test_voltage_difference_can_preserve_sampled_logic_without_qualification(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)/'ref.csv';c=Path(d)/'candidate.csv'
            r.write_text('time_s,v(pllout)\n0,0\n1e-12,0\n2e-12,1.8\n')
            c.write_text('time_s,v(PLLOUT)\n1e-12,0.00003\n2e-12,1.79997\n')
            value=assess(r,c)
            self.assertTrue(value['saved_sample_logic_agreement'])
            self.assertTrue(value['metrics']['v(pllout)']['all_native_sample_distances_exceed_global_channel_error'])
            self.assertFalse(value['physical_correlation_qualified']);self.assertFalse(value['unsaved_hazards_assessed'])

    def test_small_voltage_error_at_threshold_can_change_readback(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)/'ref.csv';c=Path(d)/'candidate.csv'
            r.write_text('time_s,v(pllout)\n0,0.8999999\n2e-12,0.8999999\n')
            c.write_text('time_s,v(pllout)\n1e-12,0.9000001\n2e-12,0.9000001\n')
            value=assess(r,c)
            self.assertFalse(value['saved_sample_logic_agreement'])
            self.assertEqual(value['sampled_logic_mismatches'],2)


if __name__=='__main__':unittest.main()
