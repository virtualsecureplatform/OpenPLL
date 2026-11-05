import unittest
from buffer_measured_loads_v3 import measured_electrical_targets,noninverting_identity

class MeasuredLoadBuffer(unittest.TestCase):
    def test_identity_syntax_is_not_confused_with_other_functions(self):
        for expression in ('A','(A)',' ((A)) '):self.assertTrue(noninverting_identity(expression))
        for expression in ('!A','~A','B','A&B','1','A if B else 0','(A','A()'):
            with self.subTest(expression=expression):self.assertFalse(noninverting_identity(expression))

    def test_only_measured_slew_and_capacitance_rows_are_selected(self):
        text='''Startpoint: not_a_target
-1.000000 slack (VIOLATED)
max slew
Pin Limit Slew Slack
sink/A 1.00 1.60 -0.60 (VIOLATED)
max capacitance
Pin Limit Cap Slack
driver/Y 0.20 0.33 -0.13 (VIOLATED)
Pin Width Width Slack
clock/CLK (high) 0.15 0.05 -0.10 (VIOLATED)
'''
        rows=measured_electrical_targets(text)
        self.assertEqual([r['pin'] for r in rows],['sink/A','driver/Y'])
        self.assertEqual([r['kind'] for r in rows],['slew_ns','capacitance_pf'])
        self.assertEqual(rows[1]['actual'],0.33)
    def test_met_and_untyped_rows_do_not_trigger_an_eco(self):
        self.assertEqual(measured_electrical_targets('driver/Y 0.20 0.33 -0.13 (VIOLATED)'),[])
        self.assertEqual(measured_electrical_targets('Pin Limit Cap Slack\ndriver/Y 0.20 0.10 0.10 (MET)'),[])
