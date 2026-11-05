import unittest
from compare_selected_dco_startup_aligned import aligned,metrics,window_frequency


class StartupAlignmentTest(unittest.TestCase):
    def waveform(self,shift_ns):
        rows=[]
        for half in range(101):
            t=half*.5;reset=1.8 if t>=5 else 0
            output=1.8 if t>=8 and int((t-8)/1.25)%2==0 else 0
            rows.append([(t+shift_ns)*1e-9,output,reset])
        return rows

    def test_absolute_time_translation_does_not_change_aligned_frequency(self):
        a,am=aligned(self.waveform(0),1,2);b,bm=aligned(self.waveform(180),1,2)
        self.assertAlmostEqual(bm['reset_release_ns']-am['reset_release_ns'],180)
        result=metrics(a,b,30)
        self.assertAlmostEqual(result['common']['difference_ppm'],0,places=6)
        self.assertEqual(result['early']['window_after_first_rise_ns'],[10,20])
        self.assertEqual(result['late']['window_after_first_rise_ns'],[20,30])

    def test_rejects_multiple_reset_releases(self):
        rows=self.waveform(0)
        for row in rows:
            if 20e-9<row[0]<22e-9:row[2]=0
        with self.assertRaisesRegex(ValueError,'exactly one'):aligned(rows,1,2)

    def test_short_or_sparse_windows_cannot_produce_comparison(self):
        with self.assertRaisesRegex(ValueError,'coverage'):metrics([0,2.5,5],[0,2.5,5],10)
        with self.assertRaisesRegex(ValueError,'three'):window_frequency([1,2],0,3)

    def test_early_and_late_windows_expose_frequency_change(self):
        candidate=[0,2,4,6,8,10,12,14,16,18,20,23,26,29,32,35,38]
        reference=list(range(0,41,2));result=metrics(candidate,reference,40)
        self.assertLess(result['late']['candidate']['frequency_mhz'],result['early']['candidate']['frequency_mhz'])
        self.assertLess(result['late']['difference_ppm'],result['early']['difference_ppm'])


if __name__=='__main__':unittest.main()
