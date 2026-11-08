import unittest
import numpy as np
from compare_keeper_native_timestep import compare_waveforms

class TimestepComparison(unittest.TestCase):
    def waveform(self,shift=0,period=2.5):
        times=[0.];values=[0.]
        for i in range(104):
            rise=1.+i*period+shift
            if rise+1.3>=260:break
            times.extend([rise-.1,rise+.1,rise+1.15,rise+1.35]);values.extend([0.,1.8,1.8,0.])
        times.append(260.);values.append(0.)
        return np.column_stack([np.array(times)*1e-9,values])
    def test_constant_edge_shift_seen_despite_identical_frequency(self):
        r=compare_waveforms(self.waveform(),self.waveform(.005))
        self.assertAlmostEqual(r['frequency_difference_ppm'],0,places=6)
        for d in r['edge_comparison'].values():
            self.assertTrue(d['equal_post_reset_edge_counts']);self.assertAlmostEqual(d['maximum_absolute_difference_ps'],5,places=5)
        self.assertFalse(r['numerical_accuracy_qualified'])
    def test_frequency_error_and_edge_count_change_reported(self):
        r=compare_waveforms(self.waveform(),self.waveform(period=2.6))
        self.assertLess(r['frequency_difference_ppm'],-30000)
        self.assertFalse(r['edge_comparison']['rising_ns']['equal_post_reset_edge_counts'])
        self.assertIsNone(r['edge_comparison']['rising_ns']['maximum_absolute_difference_ps'])
    def test_incomplete_waveform_rejected(self):
        with self.assertRaises(ValueError):compare_waveforms(self.waveform()[:-1],self.waveform())
    def test_nonfinite_waveform_rejected(self):
        a=self.waveform();a[10,1]=np.nan
        with self.assertRaises(ValueError):compare_waveforms(a,self.waveform())
    def test_stationary_output_rejected(self):
        a=self.waveform();a[:,1]=0
        with self.assertRaises(ValueError):compare_waveforms(a,self.waveform())

if __name__=='__main__':unittest.main()
