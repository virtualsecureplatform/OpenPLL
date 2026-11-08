import unittest
from audit_keeper_receiver_closure_cost import graph,closure


class DiffusionClosureCost(unittest.TestCase):
    def devices(self):
        return graph('''X1 out command 0 0 sky130_fd_pr__nfet_01v8 w=1 l=1
X2 downstream out 0 0 sky130_fd_pr__nfet_01v8 w=1 l=1
X3 tail downstream 0 0 sky130_fd_pr__nfet_01v8 w=1 l=1
X4 unrelated other 0 0 sky130_fd_pr__nfet_01v8 w=1 l=1
''')

    def test_transitive_loads_required_but_unrelated_devices_excluded(self):
        d,a=self.devices()
        result,selected=closure(d,a,{'X1'})
        self.assertTrue(result['closure_reached'])
        self.assertEqual(selected,{'X1','X2','X3'})
        self.assertEqual(result['rounds'][0]['added_primitives'],1)

    def test_cost_limit_reports_required_lower_bound_without_claiming_closure(self):
        d,a=self.devices()
        result,selected=closure(d,a,{'X1'},limit=2)
        self.assertFalse(result['closure_reached'])
        self.assertTrue(result['stopped_at_cost_limit'])
        self.assertEqual(result['required_primitive_lower_bound'],3)
        self.assertEqual(selected,{'X1','X2'})

    def test_rails_do_not_force_entire_circuit_and_missing_selection_rejected(self):
        d,a=self.devices()
        self.assertNotIn('0',a)
        with self.assertRaises(ValueError):closure(d,a,{'missing'})


if __name__=='__main__':
    unittest.main()
