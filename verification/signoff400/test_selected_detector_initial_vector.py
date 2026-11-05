import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from run_selected_detector_phase_probe_v4 import reuse_initial_vector

class DetectorInitialVectorTests(unittest.TestCase):
    def fixture(self,p):
        manifest=p/'native_manifest';manifest.write_text('native candidate')
        raw=p/'original_raw_not_read'
        vector=p/'initial_voltage_vector.json';vector.write_text(json.dumps(dict(variable_names=['TIME','V(n)','V(xpll:m)'],values=[0,1.8,.2],time_s=0)))
        receipt=dict(input_sha256={str(raw):'b'*64,str(manifest):sha(manifest)},artifacts={str(vector):sha(vector)})
        (p/'assessment.json').write_text(json.dumps(receipt))
        (p/'status.json').write_text(json.dumps(dict(state='full_initial_voltage_snapshot_captured')))
        return manifest,raw,vector
    def test_expanded_cut_binds_root_and_hierarchical_native_voltages(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m,r,_=self.fixture(p)
            values,pins,digest=reuse_initial_vector(p,m,r,['n','m'])
            self.assertEqual(values,{'n':1.8,'m':.2});self.assertEqual(digest,'b'*64)
            self.assertNotIn(str(r),pins)
    def test_missing_boundary_and_modified_vector_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m,r,v=self.fixture(p)
            with self.assertRaises(ValueError):reuse_initial_vector(p,m,r,['missing'])
            v.write_text('{}')
            with self.assertRaises(ValueError):reuse_initial_vector(p,m,r,['n'])

if __name__=='__main__':unittest.main()
