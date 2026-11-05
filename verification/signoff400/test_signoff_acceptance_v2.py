import copy
import json
import unittest
import numpy as np

from acceptance_v2 import evaluate,REQUIREMENTS


class AcceptanceControls(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads(REQUIREMENTS.read_text())
        self.stop=30000
        self.events=self.trace(400,128)
        self.controls=[[0,128]]

    def trace(self,mode,code,stop=None):
        stop=self.stop if stop is None else stop
        return {kind:[[float(t),code,0] for t in np.arange(0,stop+81,40 if kind!='OUT' else 1000/mode)]
                for kind in ('REF','DIV','OUT')}

    def check(self,events=None,controls=None,mode=400,stop=None):
        return evaluate(self.events if events is None else events,self.controls if controls is None else controls,
                        mode,280,self.stop if stop is None else stop,self.spec)

    def test_only_400mhz_and_exact_final_horizon(self):
        for mode in (400,):
            r=self.check(self.trace(mode,128),mode=mode)
            self.assertTrue(r['passed'])
            self.assertEqual(r['windows'][-1]['end_ns'],self.stop)
            self.assertFalse(r['release_qualified'])

    def test_inclusive_operating_code_boundaries(self):
        for code in (8,247):
            self.assertTrue(self.check(self.trace(400,code),[[0,code]])['passed'])

    def test_old_rail_only_false_positives_rejected(self):
        for code in (7,248):
            r=self.check(self.trace(400,code),[[0,code]])
            self.assertFalse(r['passed'])
            self.assertTrue(r['windows'][-1]['fine_outside_operating_range'])

    def test_between_edge_tuning_excursion_rejected(self):
        # No clock-edge snapshot sees this short invalid excursion.
        controls=[[0,128],[29998.1,7],[29998.2,128]]
        self.assertFalse(self.check(controls=controls)['passed'])

    def test_truncated_divided_tail_cannot_move_observation_end(self):
        self.events['DIV']=[r for r in self.events['DIV'] if r[0]<self.stop-100]
        r=self.check()
        self.assertFalse(r['passed'])
        self.assertEqual(r['failure'],'missing_final_DIV_edges')

    def test_truncated_output_tail_rejected(self):
        self.events['OUT']=[r for r in self.events['OUT'] if r[0]<self.stop-10]
        self.assertEqual(self.check()['failure'],'missing_final_OUT_edges')

    def test_actual_reference_guard_is_required(self):
        self.events['REF']=[r for r in self.events['REF'] if r[0]<self.stop]
        self.assertEqual(self.check()['failure'],'reference_guard_edge_required')

    def test_missing_interior_reference_cannot_be_interpolated_away(self):
        self.events['REF']=[[0,128,0],[30000,128,0],[30040,128,0]]
        self.assertFalse(self.check()['passed'])

    def test_missing_tuning_trace_cannot_pass(self):
        r=evaluate(self.events,None,400,280,self.stop,self.spec)
        self.assertFalse(r['passed'])
        self.assertEqual(r['failure'],'complete_control_change_trace_required')

    def test_positive_and_negative_phase_bias(self):
        for offset in (-.3,.3):
            events=copy.deepcopy(self.events)
            events['DIV']=[[r[0]+offset,*r[1:]] for r in events['DIV'] if r[0]+offset>=0]
            self.assertFalse(self.check(events)['passed'])

    def test_phase_span_and_drift(self):
        events=copy.deepcopy(self.events)
        events['DIV']=[[r[0]+(.2 if i%2 else -.2),*r[1:]] for i,r in enumerate(events['DIV']) if r[0]>.2]
        self.assertFalse(self.check(events)['passed'])
        events=copy.deepcopy(self.events)
        events['DIV']=[[r[0]-.2+.4*r[0]/self.stop,*r[1:]] for r in events['DIV'] if r[0]>.2]
        result=self.check(events)
        self.assertFalse(result['passed'])
        self.assertTrue(abs(result['windows'][-1]['phase_drift_ns'])>.05)

    def test_exact_period_cycle_slip_is_detected(self):
        for kind,time in [('DIV',28000),('OUT',28000)]:
            events=copy.deepcopy(self.events)
            events[kind]=[r for r in events[kind] if r[0]!=time]
            r=self.check(events)
            self.assertFalse(r['passed'])
            self.assertTrue(r['windows'][-1]['cycle_gaps'][kind])

    def test_frequency_failure(self):
        events=self.trace(401,128)
        self.assertFalse(self.check(events)['passed'])

    def test_acquisition_confirmation_deadline(self):
        stop=260000
        events=self.trace(400,128,stop)
        for kind in events:events[kind]=[r for r in events[kind] if r[0]>=220000]
        self.assertFalse(self.check(events,stop=stop)['passed'])

    def test_insufficient_sustained_windows(self):
        self.assertFalse(self.check(stop=15000)['passed'])

    def test_malformed_inputs(self):
        for bad in ('nan','fractional','reversed'):
            events=copy.deepcopy(self.events)
            if bad=='nan':events['OUT'][1][0]=float('nan')
            elif bad=='fractional':events['OUT'][1][1]=8.5
            else:events['OUT'][1][0]=events['OUT'][0][0]
            with self.assertRaises(ValueError):self.check(events)
        with self.assertRaises(ValueError):self.check(mode=450)


if __name__=='__main__':
    unittest.main()
