import copy
import json
import unittest
from fractions import Fraction
import numpy as np
from acceptance_v4 import evaluate, exact_grid_metrics, REQUIREMENTS
from test_signoff_acceptance_v3 import AcceptanceControls as PreviousControls


class ExistingControls(PreviousControls):
    def check(self,events=None,controls=None,mode=400,stop=None):
        return evaluate(self.events if events is None else events,self.controls if controls is None else controls,
            mode,280,self.stop if stop is None else stop,self.spec)


class ExactBoundaryControls(unittest.TestCase):
    def trace(self,span_ps):
        stop=220010
        events={k:[[float(t),128,0]for t in np.arange(10,stop+81,2.5 if k=='OUT'else 40)]for k in ['REF','DIV','OUT']}
        events['DIV']=[[r[0]+(-125 if i%2 else span_ps-125)/1000,128,0]for i,r in enumerate(events['DIV'])]
        return events,stop

    def test_limit_is_inclusive_without_an_epsilon(self):
        profile=json.loads(REQUIREMENTS.read_text())
        for span,expected in [(249,True),(250,True),(251,False)]:
            events,stop=self.trace(span)
            r=evaluate(events,[[0,128]],400,0,stop,profile)
            self.assertEqual(r['passed'],expected,span)
            self.assertEqual(r['windows'][-1]['phase_span_ns'],span/1000)
            self.assertTrue(all(w['phase_statistics_method']=='exact_integer_picosecond_grid'for w in r['windows']))

    def test_real_sub_picosecond_excess_is_rejected(self):
        events,stop=self.trace(250.001)
        r=evaluate(events,[[0,128]],400,0,stop,json.loads(REQUIREMENTS.read_text()))
        self.assertFalse(r['passed'])
        self.assertTrue(all(w['phase_span_ns']>.25 for w in r['windows']))

    def test_large_absolute_time_does_not_change_the_span(self):
        for origin in [0,220000,440000]:
            ref=np.array([origin+t/1000 for t in [0,40000,80000,120000]])
            div=np.array([origin+t/1000 for t in [100,40350,80100]])
            out=np.array([origin+t/1000 for t in [0,2500,5000]])
            self.assertEqual(exact_grid_metrics(ref,div,out,25,400)['span'],Fraction(1,4))

    def test_exact_drift_and_real_excess(self):
        ref=np.array([0,40,80,120],dtype=float);out=np.array([0,2.5,5])
        self.assertEqual(exact_grid_metrics(ref,np.array([0,40.025,80.05]),out,25,400)['drift'],Fraction(1,20))
        self.assertGreater(exact_grid_metrics(ref,np.array([0,40.025,80.051]),out,25,400)['drift'],Fraction(1,20))

    def test_off_grid_data_is_not_rounded(self):
        self.assertIsNone(exact_grid_metrics(np.array([0,40,80]),np.array([.0001,40.0001,80]),np.array([0,2.5,5]),25,400))

    def test_nonuniform_reference_does_not_use_uniform_phase_formula(self):
        self.assertIsNone(exact_grid_metrics(np.array([0,40,81]),np.array([1,41,80]),np.array([0,2.5,5]),25,400))


del PreviousControls

if __name__=='__main__':unittest.main()
