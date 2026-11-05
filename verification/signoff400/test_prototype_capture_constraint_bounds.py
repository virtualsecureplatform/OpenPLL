import unittest
from derive_prototype_capture_constraints import bounds


class ConstraintBoundTests(unittest.TestCase):
    def test_signed_phase_brackets_become_positive_constraints_with_allowance(self):
        point=dict(observed_brackets=[dict(kind='data_fall',latest_sampled_clean_before_ps=-750,
                                           earliest_sampled_clean_after_ps=250)])
        self.assertEqual(bounds(point,'data_fall',10),(760,260))

    def test_missing_or_invalid_bracket_cannot_become_a_default_constraint(self):
        for before,after in ((None,250),(-250,None),(0,250),(-250,0),(250,250)):
            point=dict(observed_brackets=[dict(kind='async_release',latest_sampled_clean_before_ps=before,
                                               earliest_sampled_clean_after_ps=after)])
            with self.assertRaisesRegex(ValueError,'both sides'):bounds(point,'async_release',10)


if __name__=='__main__':unittest.main()
