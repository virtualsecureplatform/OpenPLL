import unittest
from benchmark_keeper_corrected_reduced_replay_v2 import ROOT, checked_backend


class CorrectedBackend(unittest.TestCase):
    def record(self):
        binary = str(ROOT / 'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce')
        return dict(input_sha256={binary: 'pinned'}, native_executable=binary,
                    native_executable_sha256='pinned', BSIM_PBSWGD_default_corrected=True)

    def test_matching_corrected_identity(self):
        checked_backend(self.record(), 'pinned')

    def test_old_executable_rejected_despite_corrected_label(self):
        record = self.record()
        old = str(ROOT / 'build/tools/xyce_umfpack_value_gather_001/Xyce')
        record.update(native_executable=old, input_sha256={old: 'pinned'})
        with self.assertRaises(ValueError):
            checked_backend(record, 'pinned')

    def test_missing_or_inconsistent_identity_rejected(self):
        for key in ('input_sha256', 'native_executable', 'native_executable_sha256',
                    'BSIM_PBSWGD_default_corrected'):
            record = self.record()
            del record[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                checked_backend(record, 'pinned')
        with self.assertRaises(ValueError):
            checked_backend(self.record(), 'different')

    def test_historical_backend_pin_does_not_change_explicit_active_identity(self):
        record = self.record()
        record['input_sha256']['/other/Xyce'] = 'pinned'
        checked_backend(record, 'pinned')


if __name__ == '__main__':
    unittest.main()
