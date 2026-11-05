import tempfile,unittest,json
from pathlib import Path
from selected_model_registry import fingerprint,create,validate
from common_v3 import sha

class RegistryTests(unittest.TestCase):
    def test_identity_is_independent_of_controller_and_invalidates_physical_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);model=p/'analog';model.write_text('model');det=p/'detector';det.write_text('timing')
            receipt=p/'point.json';receipt.write_text(json.dumps(dict(signals={'v(pllout)':dict(rising_edges_200_260ns=23,mean_frequency_mhz=392.31)},coarse_code=dict(window_codes=[20]),dco_code=dict(window_codes=[111]))))
            a=dict(input_sha256={str(model):sha(model)},operating_point=dict(corner='tt',temperature_c=27,supply_v=1.8))
            i=dict(input_sha256={str(det):sha(det)})
            v=create(a,i,[receipt],p/'registry.json')
            rtl=p/'controller.v';rtl.write_text('first version');key=v['analog_key'];rtl.write_text('new version')
            self.assertEqual(validate(v)['analog_key'],key)
            model.write_text('changed load')
            with self.assertRaises(ValueError):validate(v)
    def test_fingerprint_is_order_independent_and_rejects_nan(self):
        self.assertEqual(fingerprint(dict(a=1,b=2)),fingerprint(dict(b=2,a=1)))
        with self.assertRaises(ValueError):fingerprint(dict(a=float('nan')))

if __name__=='__main__':unittest.main()
