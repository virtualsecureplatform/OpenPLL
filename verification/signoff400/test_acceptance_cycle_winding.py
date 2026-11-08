import unittest
from common_v3 import spec
from acceptance_v4 import evaluate as old_evaluate
from acceptance_v5 import evaluate


class CycleWinding(unittest.TestCase):
    def events(self,div_period_ps=40000,out_period_ps=2500,branch=False,missing=False):
        stop_ps=22000000
        ref=[[t/1000,128] for t in range(0,stop_ps+80001,40000)]
        div=[]
        for i,t in enumerate(range(0,stop_ps+40001,div_period_ps)):
            if missing and i==300:continue
            if branch:t+=19999+(2 if i%2 else -2)
            div.append([t/1000,128])
        out=[[t/1000,128] for t in range(0,stop_ps+2501,out_period_ps)]
        return dict(REF=ref,DIV=div,OUT=out)

    def assess(self,events,reader=evaluate):
        return reader(events,[[0,128]],400,0,22000,spec())

    def test_slow_full_cycle_winding_without_any_clock_gap(self):
        events=self.events(40400,2525)
        old=self.assess(events,old_evaluate)
        new=self.assess(events)
        self.assertTrue(all(not w['cycle_slip'] for w in old['windows']))
        self.assertTrue(all(w['phase_full_cycle_excursion'] and w['cycle_slip'] for w in new['windows']))
        self.assertTrue(all(not any(w['cycle_gaps'].values()) for w in new['windows']))
        self.assertFalse(new['passed'])

    def test_small_motion_across_wrapped_phase_boundary_is_not_full_cycle(self):
        report=self.assess(self.events(branch=True))
        self.assertTrue(all(not w['phase_full_cycle_excursion'] and not w['cycle_slip'] for w in report['windows']))

    def test_missing_edge_detection_preserved(self):
        report=self.assess(self.events(missing=True))
        self.assertTrue(any(w['cycle_gaps']['DIV'] and w['cycle_slip'] for w in report['windows']))

    def test_ideal_locked_trace_still_passes(self):
        report=self.assess(self.events())
        self.assertTrue(report['passed'])
        self.assertTrue(all(not w['cycle_slip'] for w in report['windows']))


if __name__=='__main__':unittest.main()
