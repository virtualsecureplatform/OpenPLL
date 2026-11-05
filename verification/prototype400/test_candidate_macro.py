"""Reject stale RTL and unrelated digital views at the assembly boundary."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import sha
from candidate_macro import digital_views


class CandidateMacro(unittest.TestCase):
    def prepare(self, root):
        route, checks, placed = (root / n for n in ('route', 'checks', 'placed'))
        for folder in (route / 'signoff', checks, placed):
            folder.mkdir(parents=True)
        rtl = root / 'source.v'; rtl.write_text('corrected startup')
        for name in ('route.v', 'route.odb', 'digital.lef'):
            (route / name).write_text(name)
        gds = route / 'signoff/route.gds'; gds.write_text('gds')
        log = checks / 'proof.log'; log.write_text('proof')
        def save(path, value):
            path.write_text(json.dumps(value))
        save(placed / 'assessment.json', dict(placement_completed=True,
             input_sha256={str(rtl):sha(rtl)}, artifacts={}))
        save(route / 'assessment.json', dict(digital_routing_completed=True, nominal_rc_extracted=True,
             input_sha256={str(placed / 'assessment.json'):sha(placed / 'assessment.json')},
             artifacts={str(route / n):sha(route / n) for n in ('route.v','route.odb','digital.lef')}))
        equivalent = checks / 'equivalence.json'
        save(equivalent, dict(all_transition_and_output_functions_equivalent=True,
             corrupted_reset_function_rejected=True, input_sha256={str(route / 'route.v'):sha(route / 'route.v')},
             artifacts={str(log):sha(log)}))
        layout = route / 'signoff/assessment.json'
        save(layout, dict(diagnostic_physical_pass=True,
             sha256={str(gds):sha(gds),str(route / 'route.odb'):sha(route / 'route.odb')}))
        save(checks / 'assessment.json', dict(digital_layout_pass=True,
             route_equivalence=str(equivalent),route_equivalence_sha256=sha(equivalent),
             digital_layout_assessment=str(layout),digital_layout_assessment_sha256=sha(layout)))
        return route, checks, placed, rtl

    def test_matching_views_are_returned_with_receipt_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            route, checks, placed, rtl = self.prepare(Path(temp))
            with patch('candidate_macro.source_pins', return_value={str(rtl):sha(rtl)}):
                views = digital_views(route, checks, placed)
            self.assertEqual(views['gds'], str(route / 'signoff/route.gds'))
            self.assertIn(str(placed / 'assessment.json'), views['evidence_sha256'])

    def test_repaired_route_can_descend_through_a_pinned_earlier_route(self):
        with tempfile.TemporaryDirectory() as temp:
            route, checks, placed, rtl = self.prepare(Path(temp))
            ancestor = route.parent / 'before_repair'; ancestor.mkdir()
            ancestor_receipt = ancestor / 'assessment.json'
            current = route / 'assessment.json'
            ancestor_receipt.write_bytes(current.read_bytes())
            report = json.loads(current.read_text())
            report['input_sha256'] = {str(ancestor_receipt):sha(ancestor_receipt)}
            current.write_text(json.dumps(report))
            with patch('candidate_macro.source_pins', return_value={str(rtl):sha(rtl)}):
                self.assertEqual(digital_views(route, checks, placed)['route'], str(route))

    def test_layout_side_receipts_do_not_masquerade_as_ancestry(self):
        for side_first in (False,True):
            with self.subTest(side_first=side_first), tempfile.TemporaryDirectory() as temp:
                route, checks, placed, rtl = self.prepare(Path(temp))
                side = route / 'side'; side.mkdir()
                receipt = side / 'assessment.json'
                receipt.write_text(json.dumps(dict(sha256={},diagnostic_physical_pass=True)))
                path = route / 'assessment.json'; report = json.loads(path.read_text())
                parents = report['input_sha256']
                extra = {str(receipt):sha(receipt)}
                report['input_sha256'] = {**extra,**parents} if side_first else {**parents,**extra}
                path.write_text(json.dumps(report))
                with patch('candidate_macro.source_pins',return_value={str(rtl):sha(rtl)}):
                    self.assertEqual(digital_views(route,checks,placed)['route'],str(route))

    def test_stale_source_unrelated_layout_and_modified_gds_are_rejected(self):
        for fault in ('source', 'layout', 'gds', 'placement', 'nonpass'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                route, checks, placed, rtl = self.prepare(Path(temp))
                if fault == 'source':
                    rtl.write_text('newer startup')
                elif fault == 'gds':
                    (route / 'signoff/route.gds').write_text('changed')
                elif fault == 'placement':
                    other = placed.parent / 'other'; other.mkdir()
                    (other / 'assessment.json').write_bytes((placed / 'assessment.json').read_bytes())
                    placed = other
                elif fault == 'nonpass':
                    path = checks / 'assessment.json'; r = json.loads(path.read_text())
                    r['digital_layout_pass'] = False
                    path.write_text(json.dumps(r))
                else:
                    path = checks / 'assessment.json'; r = json.loads(path.read_text())
                    other = checks / 'unrelated.json'
                    other.write_bytes((route / 'signoff/assessment.json').read_bytes())
                    r['digital_layout_assessment'] = str(other)
                    r['digital_layout_assessment_sha256'] = sha(other)
                    path.write_text(json.dumps(r))
                with patch('candidate_macro.source_pins', return_value={str(rtl):sha(rtl)}):
                    with self.assertRaises(ValueError):
                        digital_views(route, checks, placed)


if __name__ == '__main__':
    unittest.main()
