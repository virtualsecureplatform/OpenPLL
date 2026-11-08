import unittest
from benchmark_keeper_conditional_replay_memory import checked_backend
from common_v3 import ROOT
class MemoryBackend(unittest.TestCase):
    def test_exact_old_backend_pin_required(self):
        old=str(ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce');checked_backend(dict(input_sha256={old:'expected'}),'expected')
        with self.assertRaisesRegex(ValueError,'old active backend'):checked_backend(dict(input_sha256={old:'other'}),'expected')
    def test_unrelated_matching_pin_cannot_hide_mixed_backend(self):
        old=str(ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce')
        with self.assertRaisesRegex(ValueError,'old active backend'):checked_backend(dict(input_sha256={old:'expected','/other/Xyce':'corrected'}),'expected')
if __name__=='__main__':unittest.main()
