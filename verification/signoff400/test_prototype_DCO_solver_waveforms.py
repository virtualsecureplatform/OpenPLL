import copy
import unittest
from review_prototype_DCO_solver_waveforms import compare_metrics


def metric():
    return dict(corner='tt',temperature_c=27,supply_v=1.8,coarse_code=1,fine_code=128,
        measurement_start_s=20e-9,measurement_end_s=80e-9,complete_measured_cycles=26,
        observed_frequency_interval_hz=[459e6,461e6],average_frequency_hz=460e6,
        observed_duty_interval=[.51,.53],fastest_observed_frequency_including_startup_hz=461e6)


class SolverWaveformIntegrity(unittest.TestCase):
    def test_observed_envelope_retains_both_runs_without_claiming_bound(self):
        a=metric();b=metric();b['average_frequency_hz']=460.1e6;b['observed_frequency_interval_hz']=[458e6,462e6]
        r=compare_metrics(a,b)
        self.assertEqual(r['observed_frequency_envelope_hz'],[458e6,462e6])
        self.assertEqual(r['observed_mean_difference_hz'],100000)
        self.assertFalse(r['numerical_error_proven_bounded'])
        self.assertFalse(r['numerical_convergence_qualified'])
        self.assertTrue(r['solver_and_abstol_changed_together'])

    def test_mismatched_windows_or_invalid_frequency_cannot_be_compared(self):
        a=metric()
        for key,value in (('measurement_end_s',40e-9),('corner','ff'),('coarse_code',2),('average_frequency_hz',float('nan')),('complete_measured_cycles',2)):
            b=copy.deepcopy(a);b[key]=value
            with self.assertRaises(ValueError):compare_metrics(a,b)


if __name__=='__main__':unittest.main()
