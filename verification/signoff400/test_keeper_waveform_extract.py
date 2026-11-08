import tempfile,unittest
from pathlib import Path
import numpy as np
from extract_keeper_replay_waveforms import extract,completed_reference

class WaveformExtraction(unittest.TestCase):
    def source(self):return 'No. Variables: 3\nNo. Points: 2\nVariables:\n0 TIME time\n1 V(IN) voltage\n2 V(PLLOUT) voltage\nValues:\n0 0\n1.8\n0\n\n1 1e-9\n1.8\n1.5\n'
    def records(self):return {'IN':dict(expected_RAW_variable='V(IN)',role='externally_driven'),'PLLOUT':dict(expected_RAW_variable='V(PLLOUT)',role='observation_only')}
    def check(self,text,records=None):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'x.raw').write_text(text);r=extract(p/'x.raw',records or self.records(),p/'x.npy',1e-9);data=np.load(p/'x.npy');return r,data
    def test_completed_waveform_disk_array(self):
        r,a=self.check(self.source());self.assertEqual(a.shape,(2,3));self.assertEqual(a[1,2],1.5);self.assertEqual(r['samples'],2)
    def test_truncated_waveform_rejected(self):
        with self.assertRaises(ValueError):self.check(self.source().rsplit('1.5',1)[0])
    def test_nonfinite_unselected_value_rejected(self):
        records={'PLLOUT':self.records()['PLLOUT']}
        with self.assertRaises(ValueError):self.check(self.source().replace('1.8','nan'),records)
    def test_wrong_final_time_rejected(self):
        with self.assertRaises(ValueError):self.check(self.source().replace('1 1e-9','1 0.5e-9'))
    def test_incomplete_reference_rejected_before_read(self):
        with self.assertRaises(ValueError):completed_reference(dict(normal_native_completion=True))
    def test_malformed_final_voltage_rejected(self):
        with self.assertRaises(ValueError):self.check(self.source().replace('1.5','1.5junk'))
    def test_extra_sample_rejected(self):
        with self.assertRaises(ValueError):self.check(self.source()+'2 2e-9\n1\n1\n')

if __name__=='__main__':unittest.main()
