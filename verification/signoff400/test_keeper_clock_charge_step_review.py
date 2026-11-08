import copy
import unittest
from review_keeper_clock_buffer_charge_steps import compare


class ChargeStepComparison(unittest.TestCase):
    def rows(self):
        result=[]
        for corner in ('tt','ff','ss','sf','fs'):
            for ramp in (20,400,1600):
                for load in (0,100,400):
                    result.append(dict(corner=corner,full_ramp_ps=ramp,output_load_fF=load,
                        input_levels_verified=True,noninverting_response_verified=True,
                        effective_20_80_capacitance_F=[10e-15,12e-15],full_window_charge_C=[18e-15,20e-15],
                        deembedded_charge={k:{} for k in ('rising_20_80','falling_80_20','rising_full','falling_full')}))
        return result

    def test_sensitivity_is_relative_to_finer_observation(self):
        fine=self.rows()
        coarse=copy.deepcopy(fine)
        coarse[0]['effective_20_80_capacitance_F'][0]*=1.01
        result=compare(coarse,fine)
        self.assertAlmostEqual(max(v for r in result for v in r['effective_20_80_capacitance_F_coarser_minus_finer_ppm']),10000.,places=6)

    def test_incomplete_or_duplicate_grid_rejected(self):
        rows=self.rows()
        for bad in (rows[:-1],rows+[rows[0]]):
            with self.assertRaises(ValueError):compare(bad,rows)

    def test_failed_fixture_or_nonfinite_measurement_rejected(self):
        rows=self.rows()
        bad=copy.deepcopy(rows)
        bad[0]['noninverting_response_verified']=False
        with self.assertRaises(ValueError):compare(bad,rows)
        bad=copy.deepcopy(rows)
        bad[0]['full_window_charge_C'][0]=float('nan')
        with self.assertRaises(ValueError):compare(bad,rows)


if __name__=='__main__':
    unittest.main()
