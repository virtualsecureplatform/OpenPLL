import unittest
from queue_keeper_conditional_replay_BSIM_corrected import checked_backend

class ReplayBackendIdentity(unittest.TestCase):
    def record(self):return dict(native_executable='/corrected/Xyce',native_executable_sha256='new',BSIM_PBSWGD_default_corrected=True,input_sha256={'/corrected/Xyce':'new','/original/Xyce':'old'})
    def test_active_corrected_identity_accepted(self):checked_backend(self.record(),'new')
    def test_original_active_binary_rejected_despite_corrected_pin(self):
        r=self.record();r.update(native_executable='/original/Xyce',native_executable_sha256='old')
        with self.assertRaises(ValueError):checked_backend(r,'new')
    def test_missing_explicit_metadata_rejected(self):
        with self.assertRaises(ValueError):checked_backend(dict(input_sha256={'/corrected/Xyce':'new'}),'new')
    def test_hash_and_correction_flag_must_both_match(self):
        for change in [dict(native_executable_sha256='old'),dict(BSIM_PBSWGD_default_corrected=False),dict(input_sha256={'/corrected/Xyce':'old'})]:
            r=self.record();r.update(change)
            with self.assertRaises(ValueError):checked_backend(r,'new')

if __name__=='__main__':unittest.main()
