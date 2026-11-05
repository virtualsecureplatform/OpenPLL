import json
from pathlib import Path
import tempfile
import unittest
from common_v3 import save,sha
from rebind_prototype_identical_netlist_proof_v2 import run


class NestedNativeProofReceipt(unittest.TestCase):
    def test_nested_native_assessment_is_preserved_without_replacing_outer_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'old';new=root/'new';proof=root/'native';out=root/'derived'
            for p in (old,new,proof/'proof'):p.mkdir(parents=True)
            for p in (old,new):
                (p/'route.v').write_text('identical functional netlist')
                (p/'powered.v').write_text('identical powered netlist')
                save(p/'assessment.json',dict(input_sha256={},artifacts={str(p/n):sha(p/n) for n in ('route.v','powered.v')},
                     candidate_source_sha256={'source':'same'},cell_inventory={'sky130_fd_sc_hs__dfrtp_1':1},digital_routing_completed=True,router_drc_violations=0))
            nested=proof/'proof/assessment.json';save(nested,dict(native_solver_completed=True))
            save(proof/'assessment.json',dict(input_sha256={str(old/'assessment.json'):sha(old/'assessment.json'),str(old/'route.v'):sha(old/'route.v')},
                 artifacts={str(nested):sha(nested)},matched_state_primitives=1,
                 all_transition_and_output_functions_equivalent=True,corrupted_reset_function_rejected=True,
                 all_projected_pg_only_cells_have_no_signal_connections=True,passive_load_effects_excluded_from_boolean_proof=True))
            run(old,proof,new,out)
            self.assertEqual((out/'proof/assessment.json').read_bytes(),nested.read_bytes())
            outer=json.loads((out/'assessment.json').read_text())
            self.assertFalse(outer['native_proof_rerun']);self.assertFalse(outer['release_ready'])
            self.assertIn(str(out/'proof/assessment.json'),outer['artifacts'])


if __name__=='__main__':unittest.main()
