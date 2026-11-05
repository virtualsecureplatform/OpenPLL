import unittest
from run_prototype_DCO_tuning_step import step_deck,table


class DcoTuningStep(unittest.TestCase):
    def test_only_one_thermometer_source_and_observation_change(self):
        source='VCTRL127 DCO_THERM[127] 0 0\nVCTRL128 DCO_THERM[128] 0 {VDD}\nVCTRL129 DCO_THERM[129] 0 {VDD}\nVRESET RESET_N 0 PULSE(0 {VDD} 5.0n 50p 50p 80.0n 160.0n)\n.print tran v(PLLOUT)\n.tran 10.0p 80.0n 0 10.0p\n'
        result=step_deck(source)
        self.assertIn('VCTRL128 DCO_THERM[128] 0 PWL(0 {VDD} 39.9n {VDD} 40.1n 0)',result)
        self.assertEqual(sum(a!=b for a,b in zip(source.splitlines(),result.splitlines())),2)
        with self.assertRaises(ValueError):step_deck(source.replace('80.0n 160.0n','40.0n 80.0n'))

    def test_complete_printed_control_and_output_required(self):
        good='No. of Data Rows : 2\n0 0 0 1.8\n1 8e-8 1.8 0\n'
        self.assertEqual(len(table(good)),2)
        for bad in (good.replace('8e-8','7e-8'),good.replace('1.8 0','nan 0'),good.replace(' : 2',' : 3')):
            with self.assertRaises(ValueError):table(bad)


if __name__=='__main__':unittest.main()
