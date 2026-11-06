import copy,json,tempfile,unittest
from pathlib import Path
from selected_corner_boundary_bias import select,load
from common_v3 import sha

class CornerBoundaryBias(unittest.TestCase):
    def test_unique_complete_finite_zero_time_vector(self):
        v=dict(time_s=0,variable_names=['V(a)','V(XPLL:b)'],voltage_values=[.1,1.7])
        self.assertEqual(select(v,['a','b']),dict(a=.1,b=1.7))
        for field,value in [('time_s',1e-12),('voltage_values',[.1]),('voltage_values',[.1,float('nan')]),
                            ('voltage_values',[True,1.7]),('variable_names',['V(a)','v(a)'])]:
            bad=copy.deepcopy(v);bad[field]=value
            with self.assertRaises(ValueError):select(bad,['a','b'])
        with self.assertRaises(ValueError):select(v,['missing'])
    def test_corner_model_completion_and_hash_guards(self):
        with tempfile.TemporaryDirectory()as temp:
            d=Path(temp);model=d/'model.spice';model.write_text('physical model')
            vector=d/'initial_voltage_vector.json'
            vector.write_text(json.dumps(dict(time_s=0,variable_names=['V(a)'],voltage_values=[1.8])))
            receipt=d/'assessment.json'
            good=dict(corner='ff',temperature_c=27,supply_v=1.8,reset_state_only=True,
                      native_exit_zero=True,all_saved_values_finite=True,
                      input_sha256={str(model):sha(model)},artifacts={str(vector):sha(vector)})
            receipt.write_text(json.dumps(good));self.assertEqual(load(d,'ff',model,['a'])[0],{'a':1.8})
            for field,value in [('corner','tt'),('supply_v',1.6),('temperature_c',125),
                                ('native_exit_zero',False),('reset_state_only',False),
                                ('input_sha256',{}),('artifacts',{})]:
                bad=copy.deepcopy(good);bad[field]=value;receipt.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):load(d,'ff',model,['a'])
            receipt.write_text(json.dumps(good));vector.write_text('{}')
            with self.assertRaises(ValueError):load(d,'ff',model,['a'])

if __name__=='__main__':unittest.main()
