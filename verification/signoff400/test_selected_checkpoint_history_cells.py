import unittest
from map_selected_checkpoint_history_cells import locate


class LocationTests(unittest.TestCase):
    def test_unique_load_cell_internal_and_output_labels(self):
        prefix='top/sky130_fd_sc_hd__einvp_1_404/'
        result=locate({prefix+'Z':'z',prefix+'a_204_47#':'n'},['z','n'])
        self.assertEqual(result['z'],dict(cell=prefix[:-1],local_pin='Z'))
        self.assertEqual(result['n']['local_pin'],'a_204_47#')

    def test_missing_or_ambiguous_cell_mapping_rejected(self):
        for mapping in [{},{'t/sky130_fd_sc_hd__einvp_1_1/Z':'z','t/sky130_fd_sc_hd__einvp_1_2/Z':'z'}]:
            with self.assertRaisesRegex(ValueError,'unique e-inverter'):locate(mapping,['z'])

    def test_gate_driver_not_misclassified_as_retained_internal_state(self):
        with self.assertRaisesRegex(ValueError,'output or internal'):locate({'t/sky130_fd_sc_hd__einvp_1_1/A':'a'},['a'])


if __name__=='__main__':unittest.main()
