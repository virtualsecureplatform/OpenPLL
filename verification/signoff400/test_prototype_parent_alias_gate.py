"""A serializer alias proof must not waive another child's physical defects."""
import json
from pathlib import Path
import tempfile
import unittest
from build_prototype_candidate_parent_frame_v4 import digital_views
from common_v3 import sha


class ParentAliasGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.route, self.checks, self.candidate, self.alias = [base/n for n in ('route','checks','candidate','alias')]
        for p in (self.route/'signoff', self.checks, self.candidate, self.alias): p.mkdir(parents=True)
        for p in (self.route/'route.v', self.route/'digital.lef', self.route/'signoff/route.gds'): p.write_text(p.name)
        sources = {'frozen_rtl': 'same-source'}
        self.write(self.route, dict(candidate_source_sha256=sources,
            artifacts={str(self.route/'digital.lef'):sha(self.route/'digital.lef')}))
        self.write(self.checks, dict(artifacts={}, all_transition_and_output_functions_equivalent=True,
            input_sha256={str(self.route/'route.v'):sha(self.route/'route.v')}))
        self.write(self.candidate, dict(candidate_source_sha256=sources, artifacts={}))
        self.physical = dict(diagnostic_physical_pass=False,lvs_unique_match=False,
            magic_drc_rectangles=0,antenna_net_violations=0,antenna_pin_violations=0,
            power_pins_total=10,power_pins_connected=10,
            sha256={str(self.route/'signoff/route.gds'):sha(self.route/'signoff/route.gds')})
        self.proof = dict(artifacts={},digital_drc_pass=True,digital_lvs_alias_replay_pass=True,
            raw_extraction_merge_graph_proves_port_alias=True,exact_zero_R_alias_restored=True,
            original_extraction_preserved=True,source_antenna_net_violations=0)
        self.bind()

    def write(self, folder, data):
        (folder/'assessment.json').write_text(json.dumps(data))

    def bind(self):
        self.write(self.route/'signoff', self.physical)
        self.proof['input_sha256'] = {str(p):sha(p) for p in
            (self.route/'signoff/assessment.json', self.route/'digital.lef')}
        self.write(self.alias, self.proof)

    def review(self, alias=True):
        return digital_views(self.route,self.checks,self.candidate,self.alias if alias else None)

    def test_same_child_alias_proof_is_retained(self):
        selected = self.review()
        self.assertIn(str(self.alias/'assessment.json'), selected['evidence_sha256'])

    def test_missing_or_stale_alias_proof_rejected(self):
        with self.assertRaises(ValueError): self.review(False)
        self.physical['selected'] = False; self.write(self.route/'signoff', self.physical)
        with self.assertRaises(ValueError): self.review()

    def test_alias_cannot_waive_DRC_antenna_or_power_failure(self):
        for field, value in [('magic_drc_rectangles',1),('antenna_net_violations',1),
                             ('antenna_pin_violations',1),('power_pins_connected',9),('power_pins_total',0)]:
            original = self.physical[field]; self.physical[field] = value; self.bind()
            with self.subTest(field=field), self.assertRaises(ValueError): self.review()
            self.physical[field] = original

    def test_unproved_merge_or_modified_original_rejected(self):
        for field in ('raw_extraction_merge_graph_proves_port_alias','original_extraction_preserved'):
            self.proof[field] = False; self.bind()
            with self.subTest(field=field), self.assertRaises(ValueError): self.review()
            self.proof[field] = True

    def test_raw_unique_match_still_accepted_without_alias(self):
        self.physical.update(diagnostic_physical_pass=True,lvs_unique_match=True); self.bind()
        self.assertEqual(self.review(False)['master'],'IntegerPLL_ProgrammedCore')


if __name__ == '__main__': unittest.main()
