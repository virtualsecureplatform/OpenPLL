import unittest
from check_selected_boundary_waveforms import bind

class BoundaryTests(unittest.TestCase):
    def test_root_and_internal_nodes(self):
        r=bind(['REFCLK','__context_node_5'],['TIME','V(REFCLK)','V(XPLL:__context_node_5)']);self.assertTrue(r['all_bound']);self.assertEqual(len(r['bindings']),2)
    def test_missing_boundary_is_not_grounded(self):
        r=bind(['missing'],['TIME']);self.assertFalse(r['all_bound']);self.assertEqual(r['bindings'],{})
    def test_ambiguous_voltage_rejected(self):
        self.assertFalse(bind(['n'],['TIME','v(n)','v(xpll:n)'])['all_bound'])
    def test_duplicate_variables_rejected(self):
        with self.assertRaises(ValueError):bind(['n'],['v(n)','V(N)'])

if __name__=='__main__':unittest.main()
