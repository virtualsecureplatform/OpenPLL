import unittest
import tempfile,json
from pathlib import Path
from unittest.mock import patch
from contextlib import nullcontext
from collect_keeper_TT_characterization import run
from common_v3 import save,sha
from collect_keeper_TT_characterization import characterize

class TTCharacterization(unittest.TestCase):
    def points(self):return [dict(fine=i,frequency_hz=370e6+200000*i) for i in [8,110,149,182,247]]
    def holdout(self):return dict(fine=133,frequency_hz=396.6e6)
    def test_bracket_and_independent_interpolation(self):
        r=characterize(self.points(),self.holdout());self.assertEqual(r['target']['lower']['fine'],149);self.assertEqual(r['target']['upper']['fine'],182);self.assertEqual(r['independent_holdout']['predictions'][0]['error_ppm'],0);self.assertFalse(r['interpolation_accuracy_accepted'])
    def test_holdout_leakage_rejected(self):
        with self.assertRaises(ValueError):characterize([*self.points(),self.holdout()],self.holdout())
    def test_holdout_extrapolation_rejected(self):
        with self.assertRaises(ValueError):characterize(self.points(),dict(fine=1,frequency_hz=370.2e6))
    def test_nonmonotonic_fit_rejected(self):
        p=self.points();p[2]['frequency_hz']=380e6
        with self.assertRaises(ValueError):characterize(p,self.holdout())
    def test_nonfinite_frequency_rejected(self):
        with self.assertRaises(ValueError):characterize(self.points(),dict(fine=133,frequency_hz=float('nan')))
    def test_target_outside_range_reported(self):
        self.assertFalse(characterize(self.points(),self.holdout(),500e6)['target']['measured_bracket_available'])

class CollectorWorkflow(unittest.TestCase):
    def fixture(self,root):
        family=root/'family';family.mkdir();model=root/'backend_model.spice';model.write_text('synthetic fixture only')
        cases=[]
        for fine in [8,110,133,149,182,247]:
            native=root/f'fine{fine}'/'native';physical=native.parent/'physical'
            native.mkdir(parents=True);physical.mkdir()
            for folder,state in [(native,'flat_native_programming_transient_complete'),(physical,'physical_tuning_voltage_assessment_complete')]:
                save(folder/'status.json',dict(state=state));save(folder/'owner.json',dict(pid=99999999,birth='absent'))
            save(native/'inputs.json',dict(coarse=20,fine=fine,corner='tt',temperature_C=27,supply_V=1.8,input_sha256={str(model):sha(model)}))
            save(native/'assessment.json',dict(input_sha256={str(model):sha(model)},artifacts={},normal_native_completion=True,all_saved_native_values_finite=True,all_node_voltages_requested=True,stationary_requested_code=True,frequency_diagnostic=dict(frequency_mhz=370+.2*fine)))
            save(physical/'assessment.json',dict(input_sha256={str(native/'assessment.json'):sha(native/'assessment.json')},artifacts={},all_macro_and_DCO_tuning_bits_match=True,observed_bits=302,observed_endpoint_voltages=604,coarse=20,fine=fine))
            cases.append(dict(fine=fine,role='holdout' if fine==133 else 'fit',native=str(native),physical=str(physical)))
        existing=next(r for r in cases if r['fine']==149)
        save(family/'protocol.json',dict(input_sha256={str(model):sha(model)},existing_fine149_reference=existing['native'],existing_fine149_observer=existing['physical'],fit_fine_codes=[8,110,149,182,247],independent_holdout_fine=133))
        save(family/'assessment.json',dict(input_sha256={},all_five_native_controllers_initialized=True,submitted_cases=[r for r in cases if r['fine']!=149]))
        return family,cases

    def collect(self,family,output):
        with patch('collect_keeper_TT_characterization.os.sched_setaffinity'),patch('collect_keeper_TT_characterization.lease',return_value=nullcontext()):
            run(family,output,False)

    def test_completed_family_keeps_holdout_independent_and_unqualified(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);family,cases=self.fixture(root);self.collect(family,root/'result')
            result=json.loads((root/'result/assessment.json').read_text())
            self.assertEqual([r['fine'] for r in result['fit_points']],[8,110,149,182,247])
            self.assertEqual(result['independent_holdout']['measured']['fine'],133)
            self.assertTrue(result['all_native_and_physical_points_complete'])
            self.assertFalse(result['model_qualified']);self.assertFalse(result['release_ready'])

    def test_physical_receipt_from_another_capture_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);family,cases=self.fixture(root);receipt=Path(cases[0]['physical'])/'assessment.json'
            record=json.loads(receipt.read_text());record['input_sha256']={};save(receipt,record)
            with self.assertRaisesRegex(ValueError,'different native receipt'):self.collect(family,root/'result')
            self.assertFalse((root/'result/assessment.json').exists())

    def test_incomplete_native_capture_cannot_be_collected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);family,cases=self.fixture(root)
            save(Path(cases[0]['native'])/'status.json',dict(state='flat_native_programming_transient_running'))
            with self.assertRaisesRegex(RuntimeError,'owner is gone'):self.collect(family,root/'result')
            self.assertFalse((root/'result/assessment.json').exists())

if __name__=='__main__':unittest.main()

