import copy,unittest
from follow_full_corner_calibration import binding,LIB

class FullCornerBinding(unittest.TestCase):
    def fixture(self):
        m=dict(operating_point=dict(corner='ff',temperature_c=27,supply_v=1.8),startup_coarse=10,startup_fine=152)
        a=dict(end_ns=260,measurement_window_ns=[200,260],coarse_code=dict(window_codes=[10]),dco_code=dict(window_codes=[152]),signals={'v(pllout)':dict(rising_edges_200_260ns=24,mean_frequency_mhz=400.1)})
        d=f'.lib "{LIB}" ff\n.options device temp=27\nV0 VPWR 0 1.8\nV1 VPB 0 1.8\nV2 VGND 0 0\nV3 VNB 0 0\n'
        return m,a,d
    def test_matching_measured_preset(self):
        m,a,d=self.fixture();r=binding(m,a,d)
        self.assertTrue(r['observed_stationary_codes_match_request']);self.assertFalse(r['target_or_startup_qualified'])
    def test_wrong_corner_rails_or_nonstationary_code_rejected(self):
        for mode in('corner','rail','coarse','fine'):
            m,a,d=self.fixture()
            if mode=='corner':d=d.replace(' ff',' tt')
            elif mode=='rail':d=d.replace('VPB 0 1.8','VPB 0 0')
            else:a['coarse_code'if mode=='coarse'else'dco_code']['window_codes'].append(11 if mode=='coarse'else 153)
            with self.subTest(mode=mode),self.assertRaises(ValueError):binding(m,a,d)
    def test_incomplete_or_nonfinite_frequency_rejected(self):
        for field,value in(('end_ns',250),('frequency',float('nan')),('edges',2)):
            m,a,d=self.fixture()
            if field=='end_ns':a[field]=value
            elif field=='frequency':a['signals']['v(pllout)']['mean_frequency_mhz']=value
            else:a['signals']['v(pllout)']['rising_edges_200_260ns']=value
            with self.subTest(field=field),self.assertRaises(ValueError):binding(m,a,d)

if __name__=='__main__':unittest.main()
