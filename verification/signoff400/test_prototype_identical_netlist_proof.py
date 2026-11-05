import json
from pathlib import Path
import tempfile
import unittest
from common_v3 import save,sha
from rebind_prototype_identical_netlist_proof import run


class IdenticalNetlistProof(unittest.TestCase):
    def fixture(self,root):
        old=root/'old';new=root/'new';proof=root/'proof'
        for p in (old,new,proof):p.mkdir()
        for index,p in enumerate((old,new)):
            (p/'route.v').write_text('same functional netlist')
            (p/'powered.v').write_text('same powered netlist')
            (p/'route.odb').write_text('different geometry '+str(index))
            save(p/'assessment.json',dict(input_sha256={},artifacts={str(p/n):sha(p/n) for n in ('route.v','powered.v','route.odb')},
                 cell_inventory={'sky130_fd_sc_hs__dfrtp_1':1},candidate_source_sha256={'source':'same'},digital_routing_completed=True,router_drc_violations=0))
        (proof/'physical.json').write_text('original native projected graph')
        save(proof/'assessment.json',dict(input_sha256={str(old/'assessment.json'):sha(old/'assessment.json'),str(old/'route.v'):sha(old/'route.v')},
             artifacts={str(proof/'physical.json'):sha(proof/'physical.json')},matched_state_primitives=1,
             all_transition_and_output_functions_equivalent=True,corrupted_reset_function_rejected=True,
             all_projected_pg_only_cells_have_no_signal_connections=True,passive_load_effects_excluded_from_boolean_proof=True))
        return old,proof,new

    def test_changed_geometry_can_reuse_exact_logic_without_native_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old,proof,new=self.fixture(root);out=root/'rebound';run(old,proof,new,out)
            r=json.loads((out/'assessment.json').read_text())
            self.assertFalse(r['native_proof_rerun']);self.assertFalse(r['release_ready'])
            self.assertEqual((out/'physical.json').read_bytes(),(proof/'physical.json').read_bytes())
            self.assertEqual(r['input_sha256'][str(new/'route.v')],sha(new/'route.v'))

    def test_changed_functional_or_powered_netlist_is_rejected(self):
        for name in ('route.v','powered.v'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                root=Path(d);old,proof,new=self.fixture(root);(new/name).write_text('changed input')
                r=json.loads((new/'assessment.json').read_text());r['artifacts'][str(new/name)]=sha(new/name);save(new/'assessment.json',r)
                with self.assertRaises(ValueError):run(old,proof,new,root/'rebound')
                self.assertFalse((root/'rebound').exists())

    def test_incomplete_source_native_proof_cannot_be_rebound(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old,proof,new=self.fixture(root)
            p=json.loads((proof/'assessment.json').read_text());p['corrupted_reset_function_rejected']=False;save(proof/'assessment.json',p)
            with self.assertRaises(ValueError):run(old,proof,new,root/'rebound')


if __name__=='__main__':unittest.main()
