import unittest
from queue_remaining_full_corners import request

class Request(unittest.TestCase):
    def fixture(self):
        op=dict(corner='ss',temperature_c=27,supply_v=1.8)
        return dict(operating_point=op,controls=dict(coarse=47,fine=145)),dict(operating_point=op,coarse=47,fine=145,native_exit_zero=True,all_saved_values_finite=True,waveform=dict(incomplete_final_sample_discarded=False),frequency=dict(frequency_mhz=400.03))
    def test_measurement_is_guidance_only(self):
        m,a=self.fixture();r=request(m,a,'ss');self.assertTrue(r['conditional_measurement_is_request_guidance_only']);self.assertFalse(r['release_ready'])
    def test_wrong_corner_code_and_native_completion_rejected(self):
        for field,value in(('coarse',46),('fine',144),('native_exit_zero',False),('all_saved_values_finite',False),('waveform',dict(incomplete_final_sample_discarded=True))):
            m,a=self.fixture();a[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):request(m,a,'ss')
        m,a=self.fixture()
        with self.assertRaises(ValueError):request(m,a,'sf')
    def test_unmeasured_out_of_band_or_invalid_frequency_rejected(self):
        for value in(399.,401.,float('nan'),float('inf'),None):
            m,a=self.fixture();a['frequency']['frequency_mhz']=value
            with self.subTest(value=value),self.assertRaises(ValueError):request(m,a,'ss')

if __name__=='__main__':unittest.main()
