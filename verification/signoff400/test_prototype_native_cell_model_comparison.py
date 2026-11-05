import json
from pathlib import Path
import tempfile
import unittest
from compare_prototype_native_cell_models import fixtures, review


class ComparisonTests(unittest.TestCase):
    def test_off_grid_selection_preserves_each_sensitizing_state(self):
        rows = []
        for side in (0, 1):
            for load in (0, .02, .08):
                rows.append(dict(corner='tt',kind='combinational',fixture=dict(
                    master='cell',input='A',output='Y',side_inputs={'B':side},
                    full_ramp_ps=200,external_load_pf=load,inverted=bool(side))))
        before = json.dumps(rows)
        cases = fixtures(rows, 'tt')
        self.assertEqual(len(cases), 2)
        self.assertEqual([c['external_load_pf'] for c in cases], [.04, .04])
        self.assertTrue(all(c['full_ramp_ps'] == 400 for c in cases))
        self.assertEqual(json.dumps(rows), before)

    def test_paired_native_event_measurement_and_terminal_guard(self):
        def voltage(t):
            for start in (2, 18):
                if start <= t < start+.4: return 1.8*(t-start)/.4
                if start+.4 <= t < start+5.4: return 1.8
                if start+5.4 <= t < start+5.8: return 1.8*(start+5.8-t)/.4
            return 0
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'batch.prn'
            lines = ['Index TIME V(IN_0) V(OLD_0) V(NEW_0)']
            for i in range(341):
                t = i/10
                lines.append(f'{i} {t*1e-9:.15g} {voltage(t):.15g} {voltage(t-.1):.15g} {voltage(t-.3):.15g}')
            path.write_text('\n'.join(lines+['End of Xyce(TM) Simulation'])+'\n')
            rows, count = review(path,[dict(inverted=False)])
            self.assertEqual(count,341)
            for c in rows[0]['comparisons']:
                for difference in c['paired_delay_difference_ps']:
                    self.assertAlmostEqual(difference,200,places=7)
                for difference in c['paired_slew_difference_ps']:
                    self.assertAlmostEqual(difference,0,places=7)
            path.write_text('\n'.join(lines)+'\n')
            with self.assertRaisesRegex(ValueError,'incomplete native waveform'):
                review(path,[dict(inverted=False)])


if __name__ == '__main__': unittest.main()
