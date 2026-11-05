import unittest
from assess_prototype_clock_train_capture import analyze

class ClockTrainCapture(unittest.TestCase):
    def rows(self, fault=False):
        def ramp(t,edge,width=.02):return max(0.,min(1.,(t-edge)/width+.5))
        rows=[]
        for i in range(12001):
            t=i*.0025
            clock=1.8*sum(ramp(t,n)-ramp(t,n+1) for n in range(10,30,2))
            q=1.8*ramp(t,20.4,.05)
            if fault and 21.5<=t<=21.8:q=.9
            rows.append((t*1e-9,clock,1.8*ramp(t,20,.2),1.8,q))
        return rows

    def test_resolves_before_next_edge(self):
        result=analyze(self.rows(),dict(kind='data_rise',offset_ps=0))
        self.assertEqual(result['observed_pre_next_edge_rail'],1)
        self.assertLess(result['observed_resolution_ns_from_test_edge'],.5)

    def test_later_clock_cannot_hide_unresolved_rail(self):
        result=analyze(self.rows(True),dict(kind='data_rise',offset_ps=0))
        self.assertIsNone(result['observed_resolution_ns_from_test_edge'])
        rows=self.rows()
        for i,row in enumerate(rows):
            if row[0]>21e-9:rows[i]=(row[0],0,*row[2:])
        with self.assertRaises(ValueError):analyze(rows,dict(kind='data_rise',offset_ps=0))

if __name__=='__main__':unittest.main()
