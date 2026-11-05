import unittest
from assess_prototype_capture_waveforms import analyze,table


def value(points,t):
    for (a,x),(b,y) in zip(points,points[1:]):
        if a<=t<=b:return x+(y-x)*(t-a)/(b-a)
    return points[-1][1]


class CaptureWaveformControls(unittest.TestCase):
    def test_glitch_is_rejected_even_when_final_state_is_correct(self):
        clock=[(0,0),(9.9,0),(10.1,1.8),(11.9,1.8),(12.1,0),(19.9,0),(20.1,1.8),(21.9,1.8),(22.1,0),(30,0)]
        data=[(0,0),(20.9,0),(21.1,1.8),(30,1.8)]
        control=[(0,0),(1.9,0),(2.1,1.8),(30,1.8)]
        case=dict(kind='data_rise',offset_ps=1000,pretest_expected=0,final_value=0,outcome='pretest_value',separated_control=True,separated_control_pass=True)
        for output,expected in [([(0,0),(30,0)],True),([(0,0),(20.3,0),(20.4,1.8),(20.6,1.8),(20.7,0),(30,0)],False)]:
            times=sorted({t for points in (clock,data,control,output) for t,_ in points})
            rows=[(t*1e-9,*(value(p,t) for p in (clock,data,control,output))) for t in times]
            r=analyze(rows,case)
            self.assertEqual(r['separated_control_waveform_pass'],expected)
            self.assertAlmostEqual(r['measured_changing_input_slew_20_to_80_ps'],120)
            if not expected:self.assertEqual(r['output_crossing_count'],2)

    def test_missing_printed_row_and_incomplete_capture_rejected(self):
        text='No. of Data Rows : 3\nIndex time v(clk) v(d) v(ctrl) v(q)\n0 0 0 0 0 0\n1 1e-8 0 0 0 0\n2 3e-8 0 0 0 0\n'
        self.assertEqual(len(table(text)),3)
        for bad in (text.replace('1 1e-8 0 0 0 0\n',''),text.replace('2 3e-8','2 2e-8')):
            with self.assertRaises(ValueError):table(bad)


if __name__=='__main__':unittest.main()
