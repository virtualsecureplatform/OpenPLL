import copy,unittest
from queue_full_corner_calibration import candidate_request

class CandidateRequest(unittest.TestCase):
    def fixture(self):
        op=dict(corner='ff',temperature_c=27,supply_v=1.8)
        return dict(operating_point=op,controls=dict(coarse=10,fine=152)),dict(operating_point=op,coarse=10,fine=152,native_exit_zero=True,all_saved_values_finite=True,frequency=dict(frequency_mhz=400.1))
    def test_actual_measurement_selects_request_only(self):
        m,a=self.fixture();r=candidate_request(m,a)
        self.assertTrue(r['frequency_is_request_guidance_only']);self.assertFalse(r['release_ready'])
        for mhz in(399.6,400.4):
            a['frequency']['frequency_mhz']=mhz;candidate_request(m,a)
    def test_invalid_measurement_rejected(self):
        for field,value in(('coarse',11),('fine',153),('native_exit_zero',False),('all_saved_values_finite',False),('frequency',dict(frequency_mhz=float('nan'))),('frequency',dict(frequency_mhz=401)),('operating_point',dict(corner='tt',temperature_c=27,supply_v=1.8))):
            m,a=self.fixture();a[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):candidate_request(m,a)
    def test_wrong_requested_domain_rejected(self):
        m,a=self.fixture();m['operating_point']=dict(corner='tt',temperature_c=27,supply_v=1.8)
        with self.assertRaises(ValueError):candidate_request(m,a)

if __name__=='__main__':unittest.main()
