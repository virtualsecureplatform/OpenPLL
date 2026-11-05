import copy
import unittest
from merge_source_zero_C_proofs import add_pins,leaf_rows


class ProofCompositionControls(unittest.TestCase):
    def setUp(self):
        self.proof=dict(source_level_zero_row_certificate_complete=True)
        self.report=dict(all_target_rows_exactly_zero=True,nonzero_symbolic_coefficients=0,
                         rows=[dict(row=2,entire_row_exactly_zero=True,nonzero_symbolic_coefficients=0)])
        self.targets=dict(negative_nodes=[dict(row=2,original_voltage_nodes=[dict(node=3,name='physical')])])

    def test_identity_union_and_conflicts(self):
        pins={'source':'abc'};add_pins(pins,{'source':'abc','namespace':'def'})
        self.assertEqual(pins,{'source':'abc','namespace':'def'})
        with self.assertRaises(ValueError):add_pins(pins,{'source':'changed'})
        self.assertEqual(set(leaf_rows(self.proof,self.report,self.targets)),{2})

    def test_partial_approximate_duplicate_and_unbound_targets_rejected(self):
        changes=[('proof',dict(source_level_zero_row_certificate_complete=False)),
                 ('report',dict(all_target_rows_exactly_zero=False)),('report',dict(nonzero_symbolic_coefficients=1)),
                 ('report',dict(rows=[])),('report',dict(rows=self.report['rows']*2)),
                 ('report',dict(rows=[dict(row=2,entire_row_exactly_zero='true',nonzero_symbolic_coefficients=0)])),
                 ('targets',dict(negative_nodes=[dict(row=0,original_voltage_nodes=[dict(node=3,name='physical')])])),
                 ('targets',dict(negative_nodes=[dict(row=2,original_voltage_nodes=[])])),
                 ('targets',dict(negative_nodes=self.targets['negative_nodes']*2))]
        for target,change in changes:
            values={name:copy.deepcopy(getattr(self,name)) for name in ('proof','report','targets')};values[target].update(change)
            with self.subTest(target=target,change=change),self.assertRaises(ValueError):
                leaf_rows(values['proof'],values['report'],values['targets'])


if __name__=='__main__':unittest.main()
