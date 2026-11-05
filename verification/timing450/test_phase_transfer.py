import copy
import unittest
from analyze_phase_transfer import summarize

GROUP = ('ss', 1.62, 125, 20)
PHASES = (-100, -50, 0, 50)


def points():
    result = []
    for phase in PHASES:
        active = 'BBPD[0]' if phase == -100 else 'BBPD[1]'
        result.append(dict(zip(('corner', 'supply_v', 'temperature_c', 'edge_ps'), GROUP),
                           phase_ps=phase, simulation_completed=True, one_active_output=True,
                           output_waveforms={name: {'complete_two_pulses': name == active}
                                             for name in ('BBPD[0]', 'BBPD[1]')}))
    return result


class PhaseTransfer(unittest.TestCase):
    def summarize(self, rows):
        return summarize(rows, groups=(GROUP,), phases=PHASES)

    def test_bias_bracket_does_not_claim_whole_loop_pass(self):
        result = self.summarize(points())
        self.assertEqual(result['curves'][0]['transition_bracket_ps'], [-100, -50])
        self.assertEqual(result['maximum_absolute_transition_bound_ps'], 100)
        self.assertFalse(result['whole_pll_phase_requirement_pass'])
        self.assertFalse(result['release_qualified'])

    def test_partial_and_unbracketed_curves_cannot_pass(self):
        for rows in (points()[:-1], []):
            result = self.summarize(rows)
            self.assertFalse(result['all_curves_bracketed'])
            self.assertIsNone(result['maximum_absolute_transition_bound_ps'])
        rows = points()
        rows[0]['output_waveforms'] = copy.deepcopy(rows[-1]['output_waveforms'])
        self.assertFalse(self.summarize(rows)['all_curves_bracketed'])

    def test_nonmonotonic_and_ambiguous_points_cannot_bracket(self):
        rows = points()
        rows[2]['output_waveforms'] = copy.deepcopy(rows[0]['output_waveforms'])
        self.assertFalse(self.summarize(rows)['all_curves_bracketed'])
        rows = points()
        rows[1]['one_active_output'] = False
        self.assertFalse(self.summarize(rows)['all_curves_bracketed'])

    def test_duplicate_and_unexpected_points_rejected(self):
        with self.assertRaises(RuntimeError):
            self.summarize(points() + points()[:1])
        rows = points()
        rows[0]['phase_ps'] = 250
        with self.assertRaises(RuntimeError):
            self.summarize(rows)


if __name__ == '__main__':
    unittest.main()
