import unittest
from run_prototype_BBPD_numerical_holdout import tighten


class NumericalHoldout(unittest.TestCase):
    def test_only_tolerances_and_maximum_step_change(self):
        original='VDD vdd 0 1.8\n.option klu method=gear reltol=1e-5 abstol=1e-9 num_threads=1\n.tran 10p 90n 0 10p\n.end\n'
        result=tighten(original)
        self.assertIn('reltol=1e-6 abstol=1e-10',result)
        self.assertIn('.tran 10p 90n 0 5p',result)
        self.assertEqual(result.replace('reltol=1e-6 abstol=1e-10','reltol=1e-5 abstol=1e-9').replace('.tran 10p 90n 0 5p','.tran 10p 90n 0 10p'),original)

    def test_unreviewed_or_duplicate_controls_rejected(self):
        for deck in ('', '.tran 10p 90n 0 10p\n.option klu reltol=1e-5\n'):
            with self.assertRaises(ValueError):tighten(deck)


if __name__=='__main__':unittest.main()
