import unittest
from assess_selected_programming_history import summarize

class ProgrammingHistoryTest(unittest.TestCase):
    def test_unchanged_endpoint_can_contain_physical_pulse(self):
        result=summarize([(0,1.8),(1e-9,0),(2e-9,1.8)])
        self.assertTrue(result['transient_logic_excursion'])
        self.assertEqual([x['direction'] for x in result['crossings']],['fall','rise'])
        self.assertAlmostEqual(result['crossings'][0]['time_ns'],0.5)

    def test_endpoint_change_is_not_transient_excursion(self):
        self.assertFalse(summarize([(0,0),(1,1.8)])['transient_logic_excursion'])

    def test_nonfinite_and_unordered_knots_rejected(self):
        for values in [[(0,0),(0,1)],[(1,0),(0,1)],[(0,0),(1,float('nan'))]]:
            with self.assertRaises(ValueError):summarize(values)

if __name__=='__main__':unittest.main()
