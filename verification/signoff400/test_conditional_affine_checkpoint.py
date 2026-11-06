import unittest
from queue_folded_checkpoint_completion import decision

class FollowupDecision(unittest.TestCase):
    def test_normal_completion_skips_native(self):self.assertEqual(decision(dict(state='saved_state_DCO_diagnostic_complete')),'skip_original_completed')
    def test_only_explicit_budget_stop_allows_distinct_variant(self):self.assertEqual(decision(dict(state='stopped_without_qualification',reason="TimeoutError('native cap')")),'run_distinct_affine_variant')
    def test_live_or_other_failure_never_launches_variant(self):
        for status in(dict(state='saved_state_DCO_native_running'),dict(state='stopped_without_qualification',reason='RuntimeError(singular matrix)'),dict(state='stopped_without_qualification',reason='')):
            with self.subTest(status=status),self.assertRaises(ValueError):decision(status)

if __name__=='__main__':unittest.main()
