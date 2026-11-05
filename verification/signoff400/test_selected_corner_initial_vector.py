import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from selected_corner_initial_vector import reuse

class CornerVectorTest(unittest.TestCase):
    def fixture(self,root):
        base=root/'base.json';model=root/'model.spice';deck=root/'profile.spice';raw=root/'profile.raw';vector=root/'initial_voltage_vector.json'
        base.write_text('{}');model.write_text('fixture');deck.write_text('.lib "pdk.lib" ff\n');raw.write_text('fixture raw')
        vector.write_text(json.dumps(dict(time_s=0,variable_names=['V(XPLL:q)'],voltage_values=[.3])))
        pins={str(p):sha(p) for p in [base,model,deck]}
        m=dict(corner='ff',temperature_c=27,supply_v=1.8,reset_state_only=True,input_sha256=pins)
        a=dict(m,native_exit_zero=True,all_saved_values_finite=True,artifacts={str(p):sha(p) for p in [raw,vector]})
        (root/'manifest.json').write_text(json.dumps(m));(root/'assessment.json').write_text(json.dumps(a))
        return base,model,vector,a

    def test_binding_preserves_voltage_and_rejects_corner_transplant(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base,model,vector,a=self.fixture(root)
            values,pins,digest=reuse(root,'ff',base,model,['q']);self.assertEqual(values,{'q':.3});self.assertEqual(digest,sha(root/'profile.raw'))
            with self.assertRaises(ValueError):reuse(root,'ss',base,model,['q'])
            with self.assertRaises(ValueError):reuse(root,'ff',base,model,['missing'])

    def test_finite_receipt_cannot_hide_nonfinite_vector(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);base,model,vector,a=self.fixture(root)
            vector.write_text(json.dumps(dict(time_s=0,variable_names=['V(XPLL:q)'],voltage_values=[float('nan')])))
            a['artifacts'][str(vector)]=sha(vector);(root/'assessment.json').write_text(json.dumps(a))
            with self.assertRaises(ValueError):reuse(root,'ff',base,model,['q'])

if __name__=='__main__':unittest.main()
