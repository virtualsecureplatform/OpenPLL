import unittest
from compare_prototype_BBPD_corrected_models import compare


def waveform(shift=0,missing=False):
    centers=[20+shift,60+shift]
    def signal(t):
        for i,c in enumerate(centers):
            if missing and i==1:continue
            if c-.1<=t<=c+.1:return (t-c+.1)*9
            if c+.1<t<c+9.9:return 1.8
            if c+9.9<=t<=c+10.1:return (c+10.1-t)*9
        return 0
    times=sorted({0.,90.,*(c+d for c in centers for d in (-.1,0,.1,9.9,10,10.1))})
    return [(t*1e-9,0,0,1.8,signal(t),0,0,0) for t in times]


class FullModelComparisonIntegrity(unittest.TestCase):
    def test_shift_is_measured_on_union_of_different_sample_meshes(self):
        result=compare(waveform(),waveform(.001))['DN']
        self.assertTrue(result['threshold_crossing_counts_match'])
        self.assertAlmostEqual(result['maximum_paired_edge_difference_ps'],1,places=6)
        self.assertGreater(result['piecewise_linear_max_voltage_difference_v'],0)

    def test_missing_detector_event_cannot_produce_paired_timing_claim(self):
        result=compare(waveform(),waveform(missing=True))['DN']
        self.assertFalse(result['threshold_crossing_counts_match'])
        self.assertIsNone(result['maximum_paired_edge_difference_ps'])


if __name__=='__main__':unittest.main()
