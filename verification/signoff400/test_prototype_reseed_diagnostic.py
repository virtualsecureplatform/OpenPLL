import json
from pathlib import Path
import tempfile
import unittest
from common_v3 import save,sha
from reseed_prototype_loop_diagnostic import run

class ReseedDiagnostic(unittest.TestCase):
    def fixture(self,root):
        table=root/'table';table.write_text('7 8 390000000000\n7 9 400050000000\n7 10 400500000000\n')
        model=root/'models.json';save(model,dict(synthetic=True,physical_models_qualified=False,input_sha256={str(table):sha(table)},coarse=7,dco_table=str(table),seed=8))
        return model
    def test_selects_millihertz_nearest_code_without_promotion(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);m=self.fixture(root);out=root/'out';run(m,out)
            value=json.loads((out/'models.json').read_text())
            self.assertEqual(value['seed'],9)
            self.assertFalse(value['startup_seed_native_measurement_qualified'])
            self.assertTrue(value['synthetic'])
    def test_cannot_modify_qualified_models(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);m=self.fixture(root);value=json.loads(m.read_text());value['physical_models_qualified']=True;save(m,value)
            with self.assertRaises(ValueError):run(m,root/'out')

if __name__=='__main__':unittest.main()
