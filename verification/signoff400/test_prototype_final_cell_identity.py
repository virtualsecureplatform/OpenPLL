import unittest
from bind_prototype_final_cell_models import compare


class CellIdentityTests(unittest.TestCase):
    original = ('.subckt cell A Y\n'
                'X0 Y A 0 0 sky130_fd_pr__nfet_01v8_lvt w=1 l=.15\n'
                'C0 A Y -1f\nC1 Y 0 3f\n.ends cell\n')

    def test_interface_and_card_order_do_not_change_named_port_operator(self):
        reordered = ('.subckt cell Y A\n'
                     'X17 Y A 0 0 sky130_fd_pr__nfet_01v8_lvt l=.15 w=1\n'
                     'C90 0 Y 3f\nC91 Y A -1f\n.ends cell\n')
        self.assertTrue(compare({'cell':self.original},{'cell':reordered},'cell')['exact_model_identity'])

    def test_changed_device_or_clipped_signed_capacitor_is_rejected(self):
        for changed in (self.original.replace('Y A 0 0','Y Y 0 0'),
                        self.original.replace('-1f','0')):
            self.assertFalse(compare({'cell':self.original},{'cell':changed},'cell')['exact_model_identity'])

    def test_missing_master_requires_new_evidence(self):
        self.assertFalse(compare({}, {'cell':self.original},'cell')['exact_model_identity'])


if __name__=='__main__':unittest.main()
