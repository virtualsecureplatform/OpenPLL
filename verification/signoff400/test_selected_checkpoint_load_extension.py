import unittest
from audit_selected_checkpoint_load_extension import extension

class LoadExtension(unittest.TestCase):
    def test_old_devices_and_values_preserved(self):
        old='.model d D IS=1e-15\nC1 a 0 1f\nX1 a b c d mos\n'
        r=extension(old,old+'C2 b 0 2f\nX2 a b c d mos\n')
        self.assertEqual(r['added_nonlinear_cards'],1);self.assertEqual(r['added_passive_cards'],1)
    def test_changed_old_coefficient_or_definition_rejected(self):
        old='.model d D IS=1e-15\nC1 a 0 1f\n'
        for new in (old.replace('1f','2f')+'C2 a 0 3f\n',old.replace('1e-15','2e-15')+'C2 a 0 3f\n','C2 a 0 3f\n'):
            with self.subTest(new=new),self.assertRaises(ValueError):extension(old,new)
    def test_duplicate_top_level_name_rejected(self):
        with self.assertRaises(ValueError):extension('C1 a 0 1f\n','C1 a 0 1f\nC1 b 0 2f\n')

if __name__=='__main__':unittest.main()
