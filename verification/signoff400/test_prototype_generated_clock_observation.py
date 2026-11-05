import unittest
from observe_prototype_generated_clock import analyze


def row(cycle,level,tracking='0',reset='1',event='DIV'):
    return dict(event=event,dco_cycle=str(cycle),level=str(level),tracking=tracking,reset_n=reset,oscillator_reset_n=reset,fast_reset_n=reset,phase='0')


class GeneratedClockObservationIntegrity(unittest.TestCase):
    def test_startup_two_cycle_period_is_not_hidden_by_tracking_divide16(self):
        data=[row(2,1),row(3,0),row(4,1),row(12,0,'1'),row(20,1,'1'),row(28,0,'1'),row(36,1,'1')]
        r=analyze(data)
        self.assertEqual(r['observed_minimum_period_dco_cycles'],2)
        self.assertEqual(r['observed_minimum_high_dco_cycles'],1)
        self.assertEqual(r['observed_minimum_low_dco_cycles'],1)
        self.assertEqual(r['tracking_periods_dco_cycles'],[16])
        self.assertFalse(r['exhaustive_clock_bound_proved'])

    def test_reset_epoch_does_not_create_spurious_zero_cycle_period(self):
        data=[row(2,1),row(3,0),row(4,1),row(4,0,reset='0',event='RESET'),row(4,0,reset='1',event='RESET'),row(6,1),row(7,0),row(8,1)]
        self.assertEqual(analyze(data)['observed_minimum_period_dco_cycles'],2)
        with self.assertRaises(ValueError):analyze([row(2,1),row(3,1),row(4,0),row(5,1)])


if __name__=='__main__':unittest.main()
