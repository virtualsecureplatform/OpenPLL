import unittest
from queue_keeper_coarse23_characterization import checked_point, BACKEND


class BandCharacterizationGuards(unittest.TestCase):
    def records(self):
        n=dict(normal_native_completion=True,all_saved_native_values_finite=True,
               stationary_requested_code=True,native_executable_sha256=BACKEND,
               BSIM_PBSWGD_default_corrected=True,codes={'COARSE_CODE':[23],'DCO_CODE':[198]},
               frequency_diagnostic={'frequency_mhz':400.})
        p=dict(all_macro_and_DCO_tuning_bits_match=True,mismatched_endpoints=0,
               observed_bits=302,observed_endpoint_voltages=604,coarse=23,fine=198)
        d=dict(corner='tt',temperature_C=27,supply_V=1.8,coarse=23,fine=198,max_step_ps=50,simulation_ns=260)
        return n,p,d

    def test_wrong_domain_or_incomplete_physical_checks_rejected(self):
        n,p,d=self.records()
        self.assertEqual(checked_point(n,p,d,198),400.)
        for change in ({'coarse':19},{'corner':'ff'},{'max_step_ps':10}):
            with self.assertRaises(ValueError):checked_point(n,p,dict(d,**change),198)
        for change in ({'observed_endpoint_voltages':603},{'mismatched_endpoints':1}):
            with self.assertRaises(ValueError):checked_point(n,dict(p,**change),d,198)

    def test_unfinished_or_wrong_backend_capture_rejected(self):
        n,p,d=self.records()
        for change in ({'normal_native_completion':False},{'all_saved_native_values_finite':False},
                       {'native_executable_sha256':'old'},{'codes':{'COARSE_CODE':[23],'DCO_CODE':[149]}}):
            with self.assertRaises(ValueError):checked_point(dict(n,**change),p,d,198)

    def test_absent_and_nonfinite_frequency_rejected(self):
        n,p,d=self.records()
        for value in (None,{},dict(frequency_mhz=float('nan')),dict(frequency_mhz=True)):
            with self.assertRaises(ValueError):checked_point(dict(n,frequency_diagnostic=value),p,d,198)


if __name__=='__main__':
    unittest.main()
