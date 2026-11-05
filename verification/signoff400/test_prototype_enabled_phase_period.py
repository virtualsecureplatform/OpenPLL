import unittest
from screen_prototype_decision_hold_phase_v5 import fast_clock_period_ns,validate_hold_shift

class EnabledPhasePeriodTests(unittest.TestCase):
    def test_actual_period_from_constraints_and_native_edges(self):
        text='create_clock -name PLLOUT -period 2.48694354638 [get_ports PLLOUT]\n'
        period=fast_clock_period_ns(text)
        validate_hold_shift(22.382492,19.895548,.31,period)
        validate_hold_shift(18,16,.31,2)

    def test_wrong_period_or_missing_physical_latency_rejected(self):
        for values in ((22.382492,19.895548,.31,2),(18,16,0,2),(18,16,.31,float('nan'))):
            with self.assertRaises(ValueError):validate_hold_shift(*values)

    def test_ambiguous_or_invalid_clock_constraints_rejected(self):
        line='create_clock -name PLLOUT -period 2 [get_ports PLLOUT]\n'
        for text in ('',line+line,line.replace('period 2','period nan'),line.replace('period 2','period 0')):
            with self.assertRaises(ValueError):fast_clock_period_ns(text)

if __name__=='__main__':unittest.main()
