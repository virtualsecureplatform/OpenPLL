#!/usr/bin/env python3
"""Acceptance tests using independent synthetic clocks and corrupted inputs."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
from pll_verification import evaluate_trace, fingerprint


def clocks(target=100, duration=100000, offset=0):
    return {name: np.column_stack((times, np.full(len(times), 128)))
            for name, times in [('REF', np.arange(20., duration, 40)),
                                ('DIV', np.arange(20.+offset, duration, 40)),
                                ('OUT', np.arange(0., duration, 1000/target))]}


class AcceptanceTests(unittest.TestCase):
    def test_all_modes_pass_clean_clocks(self):
        for target in [100, 250, 300, 400, 500]:
            self.assertTrue(evaluate_trace(clocks(target), target, 0)['passed'])

    def test_mode_scaled_phase_limit(self):
        self.assertTrue(evaluate_trace(clocks(100, offset=.5), 100, 0)['passed'])
        self.assertFalse(evaluate_trace(clocks(500, offset=.5), 500, 0)['passed'])

    def test_frequency_error(self):
        events=clocks()
        events['OUT'][:,0] /= 1.002
        self.assertFalse(evaluate_trace(events, 100, 0)['passed'])

    def test_exact_reference_period_slip_is_not_hidden_by_wrapping(self):
        events=clocks()
        events['DIV']=np.delete(events['DIV'], -30, axis=0)
        result=evaluate_trace(events,100,0)
        self.assertFalse(result['passed'])
        self.assertTrue(any(w.get('cycle_slip') for w in result['windows']))

    def test_late_acquisition_does_not_pass_deadline(self):
        events=clocks(duration=300000)
        events['DIV'][events['DIV'][:,0]<240000,1]=255
        result=evaluate_trace(events,100,0)
        self.assertTrue(result['sustained_final_pass'])
        self.assertFalse(result['passed'])

    def test_output_only_rail_or_missing_edge_cannot_hide_between_divider_edges(self):
        events=clocks(500)
        events['OUT'][-100,1]=255
        self.assertFalse(evaluate_trace(events,500,0)['passed'])
        events=clocks(500)
        events['OUT']=np.delete(events['OUT'],-100,axis=0)
        self.assertFalse(evaluate_trace(events,500,0)['passed'])

    def test_relock_to_changed_reference_phase(self):
        events=clocks(duration=150000)
        for name in ('REF','DIV','OUT'):
            events[name][events[name][:,0]>=50000,0]+=5
        self.assertTrue(evaluate_trace(events,100,50000)['passed'])

    def test_short_and_corrupt_traces(self):
        self.assertFalse(evaluate_trace(clocks(duration=10000),100,0)['passed'])
        for value in [np.nan, np.inf, -1]:
            events=clocks(); events['OUT'][8,0]=value
            with self.assertRaises(ValueError): evaluate_trace(events,100,0)

    def test_model_content_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'nested';p.mkdir();model=p/'device.spice';model.write_text('old model')
            old=fingerprint([d],{'vdd':1.8})
            self.assertEqual(old,fingerprint([d],{'vdd':1.8}))
            model.write_text('new model')
            self.assertNotEqual(old['fingerprint'],fingerprint([d],{'vdd':1.8})['fingerprint'])
            self.assertNotEqual(old['fingerprint'],fingerprint([d],{'vdd':1.62})['fingerprint'])


if __name__ == '__main__': unittest.main()
