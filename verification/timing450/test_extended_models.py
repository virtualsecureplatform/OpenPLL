import unittest
from closure_audit import GROUPS
from verify_extended_models import bbpd_bounds, bbpd_pvt_bounds, bounded_constraints, summarize, verify_bbpd_slews


def matrix():
    return '\n'.join(f'Startpoint: x\nPath Group: {group}\nPath Type: {kind}\n0.2 slack (MET)' for kind in ('max', 'min') for group in GROUPS)


class ExtendedModelTests(unittest.TestCase):
    def test_pvt_bounds_require_complete_unique_grid(self):
        wave = {'complete_two_pulses': True, 'rising_slew_20_80_ns': [.51, .52],
                'falling_slew_80_20_ns': [.18, .19], 'high_pulse_widths_ns': [.71, .72]}
        points = [{'corner': c, 'supply_v': v, 'temperature_c': t, 'phase_ps': 50,
                   'edge_ps': 20, 'simulation_completed': True, 'exit_code': 0,
                   'two_full_pulses_observed': True,
                   'output_waveforms': {'BBPD[0]': wave, 'BBPD[1]': wave}}
                  for c in ('ss', 'tt', 'ff', 'sf', 'fs') for v in (1.62, 1.8, 1.95)
                  for t in (-40, 27, 125)]
        bounds = bbpd_pvt_bounds(points)
        self.assertEqual([bounds[k] for k in ('rise_ns', 'fall_ns', 'high_ns')], [.55, .225, .675])
        for wrong in (points[:-1], points + [points[0]],
                      points[:-1] + [{**points[-1], 'phase_ps': -50}],
                      points[:-1] + [{**points[-1], 'simulation_completed': False}]):
            with self.assertRaises(RuntimeError):
                bbpd_pvt_bounds(wrong)

    def test_native_bbpd_slew_evidence(self):
        log = '\n'.join(f'2 0.18 {value} 0 40 {edge} {port} (in)' for port in ('BBPD[0]', 'BBPD[1]')
                        for edge, value in (('^', .4), ('v', .225)))
        verify_bbpd_slews(log, {'rise_ns': .4, 'fall_ns': .225})
        for text in (log.replace('0.4', '0.1'), log.replace('0.225', 'nan'),
                     log.replace('BBPD[1]', 'wrong')):
            with self.assertRaises(RuntimeError):
                verify_bbpd_slews(text, {'rise_ns': .4, 'fall_ns': .225})

    def test_bbpd_guarded_slew_and_pulse_bounds(self):
        wave = {'complete_two_pulses': True, 'rising_slew_20_80_ns': [.372314, .331172],
                'falling_slew_80_20_ns': [.197522, .178139], 'high_pulse_widths_ns': [1.360625, 1.422056]}
        point = {'single_point_pulses_observed': True, 'temperature_option_accepted': True,
                 'analysis_window_ns': [5, 85], 'output_waveforms': {'BBPD[0]': wave, 'BBPD[1]': wave}}
        bounds = bbpd_bounds(point)
        self.assertEqual([bounds[k] for k in ('rise_ns', 'fall_ns', 'high_ns')], [.4, .225, 1.325])
        recipe = bounded_constraints('create_clock -name EVENT_$name -period 40 -waveform {0 5.0} $port\n', bounds)
        self.assertIn('-waveform {0 1.325}', recipe)
        self.assertIn('set_input_transition -rise 0.4', recipe)
        self.assertIn('set_clock_transition -fall 0.225', recipe)

    def test_bbpd_incomplete_or_invalid_point_rejected(self):
        for point in ({}, {'single_point_pulses_observed': True,
                          'temperature_option_accepted': False, 'analysis_window_ns': [5, 85]},
                      {'single_point_pulses_observed': True, 'temperature_option_accepted': True,
                       'analysis_window_ns': [5, 85], 'output_waveforms': {}}):
            with self.assertRaises(RuntimeError):
                bbpd_bounds(point)
        with self.assertRaises(RuntimeError):
            bounded_constraints('create_clock -name REFCLK -period 40 [get_ports REFCLK]',
                                {'rise_ns': .4, 'fall_ns': .225, 'high_ns': 1.325})

    def test_complete_matrix_with_electrical_violation_fails(self):
        rows, passed = summarize(matrix() + '\n1.02 (VIOLATED)')
        self.assertEqual(len(rows), 14)
        self.assertFalse(passed)

    def test_missing_clock_group_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            summarize(matrix().replace('Path Group: FINECLK', 'Path Group: wrong'))

    def test_spef_name_mismatch_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'SPEF'):
            summarize(matrix() + '\nSTA-1648 missing net')
