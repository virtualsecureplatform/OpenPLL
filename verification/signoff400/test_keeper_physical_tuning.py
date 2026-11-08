import unittest
import numpy as np
from assess_keeper_physical_tuning import expected,assess

class PhysicalTuning(unittest.TestCase):
    def test_opposite_actual_RTL_polarities(self):
        self.assertEqual([expected('DCO_THERM',i,20,149) for i in [0,148,149,254]],[0,0,1,1])
        self.assertEqual([expected('COARSETHERMAL_CODE',i,20,149) for i in [0,19,20,46]],[1,1,0,0])
    def records(self):return {'fine.macro':dict(bus='DCO_THERM',bit=0,endpoint='macro'),'fine.DCO':dict(bus='DCO_THERM',bit=0,endpoint='DCO')}
    def test_both_endpoints_match(self):
        a=np.array([[200e-9,0.,0.],[260e-9,0.01,0.02]])
        self.assertTrue(all(r['all_samples_match_expected_logic'] for r in assess(a,self.records(),20,149)))
    def test_correct_macro_does_not_hide_wrong_DCO(self):
        a=np.array([[200e-9,0.,1.8],[260e-9,0.,1.8]])
        self.assertEqual([r['all_samples_match_expected_logic'] for r in assess(a,self.records(),20,149)],[True,False])
    def test_ambiguous_voltage_fails(self):
        a=np.array([[200e-9,0.,.9],[260e-9,0.,.9]])
        self.assertFalse(assess(a,self.records(),20,149)[1]['all_samples_match_expected_logic'])
    def test_incomplete_window_rejected(self):
        with self.assertRaises(ValueError):assess(np.array([[200e-9,0.,0.],[250e-9,0.,0.]]),self.records(),20,149)

if __name__=='__main__':unittest.main()
