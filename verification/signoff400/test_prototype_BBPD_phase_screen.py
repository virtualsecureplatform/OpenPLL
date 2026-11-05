import unittest
from run_prototype_BBPD_phase_screen_v2 import metrics,table


def rows(phase=1000,second_ref=50.1):
    def pulse(t,centers):
        for center in centers:
            if center-.1<=t<=center+.1:return 1.8*(t-center+.1)/.2
            if center+.1<t<center+19.9:return 1.8
            if center+19.9<=t<=center+20.1:return 1.8*(center+20.1-t)/.2
        return 0
    ref=[10.1,second_ref];div=[c+phase/1000 for c in ref]
    times=sorted({0.,1.,1.1,1.2,5.,8.,90.,*(c+d for c in ref+div for d in (-.1,0,.1,19.9,20,20.1))})
    return [(t*1e-9,pulse(t,ref),pulse(t,div),0 if t<=1 else 1.8 if t>=1.2 else (t-1)*9,0,0) for t in times]


class BBPDObserverIntegrity(unittest.TestCase):
    def test_signed_phase_is_measured_and_wrong_frequency_rejected(self):
        for phase in (-1000,0,1000):
            result=metrics(rows(phase),phase)
            for observed in result['measured_clock_phase_ps']:self.assertAlmostEqual(observed,phase)
            self.assertFalse(result['receiver_capture_qualified'])
        with self.assertRaisesRegex(ValueError,'reference frequency'):metrics(rows(second_ref=60.1),1000)
        with self.assertRaisesRegex(ValueError,'observed phase'):metrics(rows(phase=-1000),1000)

    def test_truncated_or_nonfinite_native_table_rejected(self):
        text='No. of Data Rows : 2\n0 0 0 0 0 0 0\n1 9e-8 0 0 1.8 0 0\n'
        self.assertEqual(len(table(text)),2)
        for bad in (text.replace('9e-8','8e-8'),text.replace('1.8','nan'),text.replace('1 9e-8','2 9e-8')):
            with self.assertRaises(ValueError):table(bad)


if __name__=='__main__':unittest.main()
