import copy
import unittest
from characterize_sampled_bounds import sampled_bounds

KEY = ('ss',1.62,125,250,20)


def point():
    return dict(zip(('corner','supply_v','temperature_c','phase_ps','edge_ps'),KEY),
                exit_code=0,simulation_completed=True,output_waveforms={
                'BBPD[0]':{'complete_two_pulses':False,'maximum_v':0},
                'BBPD[1]':{'complete_two_pulses':True,'maximum_v':1.65,
                           'rising_slew_20_80_ns':[.4,.4],'falling_slew_80_20_ns':[.2,.2],
                           'high_pulse_widths_ns':[20.5,20.5],'rising_half_supply_edges_ns':[15,55]}})


class SampledBounds(unittest.TestCase):
    def bounds(self, points):
        return sampled_bounds(points,grid={KEY})

    def test_low_bound_is_independent_of_minimum_high(self):
        b=self.bounds([point()])
        self.assertAlmostEqual(b['minimum_low_ns'],19.475)
        self.assertAlmostEqual(b['minimum_high_ns'],20.475)
        self.assertLess(b['minimum_low_ns'],40-b['minimum_high_ns'])

    def test_incomplete_duplicate_wrong_pvt_rejected(self):
        for data in ([],[point(),point()]):
            with self.assertRaises(RuntimeError):self.bounds(data)
        p=point();p['temperature_c']=27
        with self.assertRaises(RuntimeError):self.bounds([p])

    def test_wrong_sign_and_nonexclusive_rejected(self):
        p=point();p['output_waveforms']['BBPD[0]']['maximum_v']=1
        with self.assertRaises(RuntimeError):self.bounds([p])
        p=point();p['output_waveforms']['BBPD[0]']=copy.deepcopy(p['output_waveforms']['BBPD[1]']);p['output_waveforms']['BBPD[1]']['complete_two_pulses']=False
        with self.assertRaises(RuntimeError):self.bounds([p])

    def test_invalid_low_interval_and_nonfinite_measurements_rejected(self):
        p=point();p['output_waveforms']['BBPD[1]']['rising_half_supply_edges_ns']=[15,25]
        with self.assertRaises(RuntimeError):self.bounds([p])
        p=point();p['output_waveforms']['BBPD[1]']['rising_slew_20_80_ns'][0]=float('nan')
        with self.assertRaises(RuntimeError):self.bounds([p])


if __name__=='__main__':unittest.main()
