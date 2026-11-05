import unittest
from review_prototype_BBPD_wide_phase import classify


class WidePhaseDecisions(unittest.TestCase):
    def test_missing_multiple_and_both_decisions_not_forced_to_binary(self):
        rows={'DN':{'detector_rising_edges_ns':[12.8]},'UP':{'detector_rising_edges_ns':[12.9]}}
        self.assertEqual([r['decision'] for r in classify(rows)],['BOTH','NONE'])
        rows['UP']['detector_rising_edges_ns']=[12.9,15]
        self.assertEqual(classify(rows)[0]['decision'],'MULTIPLE')

    def test_real_sample_order_retained(self):
        rows={'DN':{'detector_rising_edges_ns':[52.8]},'UP':{'detector_rising_edges_ns':[12.8]}}
        result=classify(rows)
        self.assertEqual([r['decision'] for r in result],['UP','DN'])
        self.assertAlmostEqual(result[1]['events'][0]['time_ns'],52.8)


if __name__=='__main__':unittest.main()
