import unittest
from compare_prototype_capture_loads import transitions


def rows(outcomes):
    return [dict(offset_ps=o,outcome=s) for o,s in zip((-1000,-500,-200,0,200,500,1000),outcomes)]


class CaptureTransitionIntegrity(unittest.TestCase):
    def test_only_a_single_observed_transition_produces_a_bracket(self):
        new='changed_value';old='pretest_value';ambiguous='ambiguous_or_unsettled'
        result=transitions(rows([new,new,new,old,old,old,old]))
        self.assertEqual(result['observed_transition_bracket_ps'],[-200,0])
        self.assertFalse(result['setup_hold_recovery_removal_qualified'])
        for states in ([new,old,new,old,old,old,old],[new,new,ambiguous,old,old,old,old],[new]*7,[old]*7):
            result=transitions(rows(states))
            self.assertFalse(result['observed_single_transition'])
            self.assertIsNone(result['observed_transition_bracket_ps'])

    def test_missing_or_duplicate_offset_is_rejected(self):
        data=rows(['changed_value']*3+['pretest_value']*4)
        for bad in (data[:-1],data+[data[0]]):
            with self.assertRaises(ValueError):transitions(bad)


if __name__=='__main__':unittest.main()
