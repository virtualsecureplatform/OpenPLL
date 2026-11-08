import unittest
from compare_keeper_masked_replay import compatible,check_decks
class MaskedReplayComparison(unittest.TestCase):
    def fixture(self):
        a=dict(normal_native_replay_complete=True,all_saved_replay_values_finite=True,PLLOUT_forced=False,sampled_boundary_replay_only=True,symbolic_boundary_reduction_used=True,native_executable_sha256='same',max_step_ps=50,shared_knot_carrier_used=True,source_representation='shared',literal_aggregated_samples_preserved=True,roundoff_audited_at_source_samples=True)
        return a,dict(a,current_type_variables_masked_from_LTE=True,voltage_LTE_control_retained=True)
    def test_matching_completed_default_and_masked_cases(self):self.assertTrue(compatible(*self.fixture()))
    def test_changed_problem_or_missing_voltage_control_rejected(self):
        for field,value in [('native_executable_sha256','different'),('max_step_ps',10),('voltage_LTE_control_retained',False),('PLLOUT_forced',True),('normal_native_replay_complete',False)]:
            a,b=self.fixture();b[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compatible(a,b)
    def test_only_current_mask_and_output_destination_may_change(self):
        original='.include "same-model"\n.options nonlin reltol=1e-5\n.tran 10p 260n 0 50p\n.print tran file=/tmp/a.raw V(out)\n'
        changed=original.replace('.tran 10p','.options timeint maskivars=1\n.tran 10p').replace('/tmp/a.raw','/tmp/b.raw')
        self.assertTrue(check_decks(original,changed))
        for invalid in [changed.replace('same-model','different-model'),changed.replace('reltol=1e-5','reltol=1e-3')]:
            with self.assertRaises(ValueError):check_decks(original,invalid)
    def test_two_masked_cases_cannot_masquerade_as_default_control(self):
        a,b=self.fixture();a['current_type_variables_masked_from_LTE']=True
        with self.assertRaises(ValueError):compatible(a,b)
if __name__=='__main__':unittest.main()
