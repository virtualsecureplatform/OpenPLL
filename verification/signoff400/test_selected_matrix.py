import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import run_selected_matrix as matrix


class MatrixTests(unittest.TestCase):
    def simulated_run(self, *args):
        output = args[2]
        output.mkdir()
        (output/'assessment.json').write_text('{}')
        return dict(state='diagnostic_simulation_completed', functional_trace_pass=True)

    def fixture(self, root, corners):
        detector = root/'detector.v'
        detector.write_text('test')
        models = {}
        for corner in corners:
            path = root/(corner+'.json')
            path.write_text('{}')
            models[corner] = (path, dict(points=[dict(coarse=20, fine=111,
                receipt=str(detector), receipt_sha256=matrix.sha(detector))],
                analog=dict(input_sha256={}), interface=dict(
                detector_rtl=str(detector), input_sha256={str(detector):matrix.sha(detector)})))
        return models

    def test_missing_corners_never_launch_simulation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(matrix, 'inventory', return_value=self.fixture(root, ['tt'])), \
                 patch.object(matrix, 'run') as run:
                report = matrix.execute([], root/'output')
            run.assert_not_called()
            self.assertEqual(len(report['measurement_requests']), 4)
            self.assertEqual(matrix.exit_status(report), 3)
            self.assertFalse(report['release_ready'])

    def test_all_sixty_cases_share_gains_and_never_qualify(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(matrix, 'inventory', return_value=self.fixture(root, matrix.CORNERS)), \
                 patch.object(matrix, 'run', side_effect=self.simulated_run) as run:
                report = matrix.execute([], root/'output', ki=4, kp=0)
            self.assertEqual(run.call_count, 60)
            self.assertEqual({call.args[3:5] for call in run.call_args_list}, {(4, 0)})
            self.assertEqual(len({call.args[8:10] for call in run.call_args_list}), 12)
            self.assertTrue(report['functional_matrix_pass'])
            self.assertEqual(matrix.exit_status(report), 0)
            self.assertFalse(report['release_ready'])
            self.assertFalse(report['physical_models_qualified'])

    def test_corner_specific_presets_keep_common_gains(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            models = self.fixture(root, matrix.CORNERS)
            presets = {corner: dict(coarse=19+i, seed=100+i, polarity=i%2)
                       for i, corner in enumerate(matrix.CORNERS)}
            for corner, (_, model) in models.items():
                model['points'][0].update(coarse=presets[corner]['coarse'], fine=presets[corner]['seed'])
            path = root/'presets.json';path.write_text(json.dumps(presets))
            with patch.object(matrix, 'inventory', return_value=models), \
                 patch.object(matrix, 'run', side_effect=self.simulated_run) as run:
                report = matrix.execute([], root/'output', ki=4, kp=0, presets_path=path)
            self.assertEqual(run.call_count, 60)
            self.assertEqual({call.args[3:5] for call in run.call_args_list}, {(4, 0)})
            for index, corner in enumerate(matrix.CORNERS):
                expected = presets[corner]
                for call in run.call_args_list[index*12:(index+1)*12]:
                    self.assertEqual(call.args[5:8], (expected['coarse'], expected['seed'], expected['polarity']))
            self.assertIn(str(path), report['input_sha256'])
            self.assertEqual(report['startup_presets'], presets)
            self.assertFalse(report['release_ready'])

    def test_corner_presets_reject_incomplete_or_noninteger_values(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'presets.json'
            path.write_text('{}')
            with self.assertRaises(ValueError):matrix.startup_presets(path,20,111,1)
            values = {c: dict(coarse=20, seed=111, polarity=1) for c in matrix.CORNERS}
            values['ff']['seed'] = True;path.write_text(json.dumps(values))
            with self.assertRaises(ValueError):matrix.startup_presets(path,20,111,1)

    def test_missing_code_stops_and_requests_measurement(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(matrix, 'inventory', return_value=self.fixture(root, matrix.CORNERS)), \
                 patch.object(matrix, 'run', side_effect=lambda *args: dict(self.simulated_run(*args), state='needs_native_tuning_points',
                    measurement_requests=[dict(coarse=20, fine=112)], functional_trace_pass=False)) as run:
                report = matrix.execute([], root/'output')
            self.assertEqual(run.call_count, 1)
            self.assertEqual(report['measurement_requests'][0]['corner'], 'tt')
            self.assertEqual(matrix.exit_status(report), 3)


if __name__ == '__main__':
    unittest.main()
