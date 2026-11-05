import tempfile,json,unittest
from pathlib import Path
from loop_v3 import load_models
from common_v3 import PROFILE,sha,source_pins
from selected_clock_timing import KEYS


class TimedLoopModelsTests(unittest.TestCase):
    def test_synthetic_timing_must_be_pinned_and_match_corner(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model=root/'physical';model.write_text('fixture')
            table=root/'table';table.write_text('20 111 400000000000\n');detector=root/'detector.v';detector.write_text('fixture')
            path=root/'models.json';clock=root/'clock.json'
            op=dict(corner='tt',temperature_c=27,supply_v=1.8)
            timing=dict(schema_version=1,diagnostic=True,release_ready=False,operating_point=op,
                input_sha256={str(model):sha(model)},reference_model_sha256={str(model):sha(model)},
                delay_ps={k:0 for k in KEYS})
            clock.write_text(json.dumps(timing))
            value=dict(op,profile_sha256=sha(PROFILE),candidate_source_sha256=source_pins(),synthetic=True,
                coarse=20,seed=111,polarity=1,dco_table=str(table),detector_rtl=str(detector),
                input_sha256={str(p):sha(p) for p in [table,detector]})
            path.write_text(json.dumps(value));self.assertTrue(load_models(path,True)['synthetic'])
            value['clock_timing']=str(clock);path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'unpinned clock'):load_models(path,True)
            value['input_sha256'][str(clock)]=sha(clock);path.write_text(json.dumps(value))
            self.assertEqual(load_models(path,True)['clock_timing'],str(clock))
            timing['operating_point']=dict(op,corner='ff');clock.write_text(json.dumps(timing))
            value['input_sha256'][str(clock)]=sha(clock);path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'operating point'):load_models(path,True)


if __name__=='__main__':unittest.main()
