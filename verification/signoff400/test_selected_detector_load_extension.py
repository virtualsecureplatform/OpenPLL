import unittest
from extend_selected_detector_loads import full_load_cells

class DetectorLoadExtensionTests(unittest.TestCase):
    def test_whole_cell_is_retained_without_unrelated_same_master(self):
        def item(identity):return dict(physical_hierarchy_identity=[identity],leaf_master='buffer')
        items={'X0':item('inside'),'X1':item('load'),'X2':item('load'),'X3':item('unrelated')}
        selected,masters=full_load_cells({'X0'},{'X1':['n']},items)
        self.assertEqual(selected,{'X0','X1','X2'});self.assertEqual(masters,{'buffer':1})
    def test_invalid_omitted_primitive_is_rejected(self):
        with self.assertRaises(ValueError):full_load_cells(set(),{'missing':[]},{})

if __name__=='__main__':unittest.main()
