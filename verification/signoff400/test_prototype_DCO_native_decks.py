import unittest
from compare_prototype_DCO_native_decks import compare

BASE='''* DCO observation
.option method=gear reltol=1e-5 abstol=1e-15 chgtol=1e-16
.include "same_model.spice"
VDD power 0 1.8
.tran 10p 80n 0 10p
.end
'''
ALT=BASE.replace('.option method','.option klu\n.option method').replace('abstol=1e-15','abstol=1e-9')


class NativeDeckIdentityControls(unittest.TestCase):
    def test_only_declared_solver_and_tolerances_can_differ(self):
        r,_=compare(BASE,ALT)
        self.assertTrue(r['all_other_native_deck_records_identical'])
        self.assertTrue(r['alternative_controls']['klu_selected'])
        self.assertFalse(r['numerical_convergence_qualified'])
        for bad in (ALT.replace('1.8','1.9'),ALT.replace('same_model','other_model'),ALT.replace('80n','40n'),ALT.replace('method=gear','method=trap'),ALT.replace('chgtol=1e-16','chgtol=1e-14')):
            with self.assertRaises(ValueError):compare(BASE,bad)

    def test_nonfinite_or_duplicate_tolerances_rejected(self):
        for bad in (ALT.replace('abstol=1e-9','abstol=nan'),ALT.replace('abstol=1e-9','abstol=1e-9 abstol=1e-12')):
            with self.assertRaises(ValueError):compare(BASE,bad)


if __name__=='__main__':unittest.main()
