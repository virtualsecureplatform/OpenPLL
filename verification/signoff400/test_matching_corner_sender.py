import json
import tempfile
import unittest
from pathlib import Path
from common_v3 import save, sha
from capture_selected_native_initial_snapshot import fingerprint
from selected_matching_corner_sender import validate


class MatchingSenderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.n=self.root/'native';self.s=self.root/'snapshot';self.w=self.root/'waveforms'
        for p in [self.n,self.s,self.w]:p.mkdir()
        (self.n/'profile.raw').write_text('fixture')
        (self.n/'profile.spice').write_text('.lib models ss\n.options device temp=27\n')
        save(self.n/'manifest.json',dict(startup_fine=145))
        save(self.s/'status.json',dict(state='full_initial_voltage_snapshot_captured'))
        save(self.w/'status.json',dict(state='native_clock_driver_waveforms_captured'))
        self.sr=dict(input_sha256={str(self.n/'manifest.json'):sha(self.n/'manifest.json'),str(self.n/'profile.raw'):sha(self.n/'profile.raw')},artifacts={},source_device_conditions=dict(corner='ss',temperature_c=27),source_file_fingerprint=fingerprint(self.n/'profile.raw'))
        save(self.s/'assessment.json',self.sr)
        self.wr=dict(input_sha256={**self.sr['input_sha256'],str(self.s/'assessment.json'):sha(self.s/'assessment.json')},artifacts={},exact_saved_knots_preserved=True,source_complete_and_all_values_finite=True)
        self.write()

    def write(self):save(self.w/'assessment.json',self.wr)
    def call(self,corner='ss'):return validate(self.n,self.s,self.w,corner)
    def test_same_source_accepted(self):self.assertEqual(self.call()[0]['corner'],'ss')
    def test_tt_sender_cannot_relabel_ss(self):
        with self.assertRaisesRegex(ValueError,'corners must match'):self.call('tt')
    def test_foreign_raw_rejected(self):
        self.wr['input_sha256'][str(self.n/'profile.raw')]='a'*64;self.write()
        with self.assertRaisesRegex(ValueError,'RAW identity'):self.call()
    def test_changed_raw_rejected_without_rehash(self):
        (self.n/'profile.raw').write_text('changed')
        with self.assertRaisesRegex(ValueError,'RAW changed'):self.call()
    def test_other_snapshot_rejected(self):
        del self.wr['input_sha256'][str(self.s/'assessment.json')];self.write()
        with self.assertRaisesRegex(ValueError,'identical initial snapshot'):self.call()
    def test_incomplete_packet_rejected(self):
        save(self.w/'status.json',dict(state='extracting_native_clock_driver_shapes'))
        with self.assertRaisesRegex(ValueError,'completed sender'):self.call()


if __name__=='__main__':unittest.main()
