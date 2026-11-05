import copy
import unittest
from compare_prototype_numerical_holdout import compare

COMMAND=['worker','--corner','tt','--codes','128','--coarse-codes','1','--max-step-ps','10','--ngspice-reltol','1e-5','--ngspice-abstol','1e-15','--build-dir','old']
METRICS=dict(corner='tt',temperature_c=27,supply_v=1.8,coarse_code=1,fine_code=128,measurement_start_s=20e-9,measurement_end_s=80e-9,
 observed_frequency_interval_hz=[399e6,401e6],average_frequency_hz=400e6,fastest_observed_frequency_including_startup_hz=450e6)


class NumericalHoldoutControls(unittest.TestCase):
    def test_tighter_same_physical_case_reports_observed_envelope(self):
        cmd=COMMAND.copy();cmd[cmd.index('--max-step-ps')+1]='5'
        m=copy.deepcopy(METRICS);m['average_frequency_hz']=400.1e6;m['observed_frequency_interval_hz']=[398e6,402e6]
        r=compare(METRICS,m,COMMAND,cmd)
        self.assertEqual(r['observed_frequency_envelope_hz'],[398e6,402e6])
        self.assertEqual(r['mean_frequency_difference_ppm'],250)
        self.assertFalse(r['numerical_convergence_qualified'])

    def test_identical_weakened_or_changed_physical_conditions_rejected(self):
        for key,value in [('--max-step-ps','10'),('--max-step-ps','20'),('--codes','8')]:
            cmd=COMMAND.copy();cmd[cmd.index(key)+1]=value
            with self.assertRaises(ValueError):compare(METRICS,METRICS,COMMAND,cmd)

    def test_changed_corner_and_shortened_capture_rejected(self):
        cmd=COMMAND.copy();cmd[cmd.index('--max-step-ps')+1]='5'
        for key,value in [('corner','ff'),('measurement_end_s',40e-9)]:
            m=copy.deepcopy(METRICS);m[key]=value
            with self.assertRaises(ValueError):compare(METRICS,m,COMMAND,cmd)


if __name__=='__main__':unittest.main()
