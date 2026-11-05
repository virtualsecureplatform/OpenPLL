from pathlib import Path
import tempfile
import unittest
from characterize_prototype_final_cell_C_grid_v2 import review


class FinalCGridReviewTests(unittest.TestCase):
    def wave(self,path):
        def pulse(t):
            for start in (2,18):
                if start<=t<start+.4:return 1.8*(t-start)/.4
                if start+.4<=t<start+5.4:return 1.8
                if start+5.4<=t<start+5.8:return 1.8*(start+5.8-t)/.4
            return 0
        rows=['Index TIME V(IN_0) V(NEW_0)']
        for i in range(1361):
            t=i*.025;rows.append(f'{i} {t*1e-9:.15g} {pulse(t):.15g} {1.8-pulse(t-.075):.15g}')
        rows.append('End of Xyce(TM) Simulation');path.write_text('\n'.join(rows)+'\n')

    def test_inverted_gate_grid_preserves_delay_and_slew_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wave.prn';self.wave(path)
            rows,count=review(path,[dict(inverted=True,full_ramp_ps=400)])
            self.assertEqual(count,1361)
            observed=rows[0]['observed']
            for label in ('rise','fall'):
                for value in observed['input_'+label+'_delay_ns']:self.assertAlmostEqual(value,.075,places=8)
                for value in observed['output_'+label+'_slew_ns']:self.assertAlmostEqual(value,.24,places=8)

    def test_wrong_fixture_ramp_and_incomplete_waveform_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wave.prn';self.wave(path)
            with self.assertRaisesRegex(ValueError,'input ramp differs'):
                review(path,[dict(inverted=True,full_ramp_ps=200)])
            path.write_text(path.read_text().replace('End of Xyce(TM) Simulation',''))
            with self.assertRaisesRegex(ValueError,'incomplete'):
                review(path,[dict(inverted=True,full_ramp_ps=400)])


if __name__=='__main__':unittest.main()
