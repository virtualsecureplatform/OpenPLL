"""Checks for provenance and CDC safeguards in the physical repair flow."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import closure
import closure_audit


class ClosureTests(unittest.TestCase):
    def test_pin_caps_use_worst_supplied_corner(self):
        with tempfile.TemporaryDirectory() as tmp:
            models = {}
            for name, cap in [('ss', .012), ('ff', .009), ('tt', .013)]:
                path = Path(tmp) / f'{name}.lib'
                path.write_text(f'library("{name}") {{ cell("buf_4") {{ pin("A") {{ direction : input; capacitance : {cap}; timing() {{ values("9"); }} }} pin("X") {{ direction : output; }} }} }}')
                models[name] = path
            self.assertEqual(closure.pin_caps(models), {'buf_4/A': .013})

    def test_parenthesized_buffer_functions_include_clock_and_compound_buffers(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / 'ss.lib'
            model.write_text('library("ss") {' + ''.join(
                f'cell("{name}") {{ pin("A") {{ direction : "input"; capacitance : .01; }} '
                f'pin("X") {{ direction : "output"; function : "{func}"; power_down_function : "(!VPWR + VGND)"; }} }}'
                for name, func in [('bufbuf_16', '(A)'), ('clkbuf_16', '( A )'), ('inv_1', '(!A)')]) + '}')
            self.assertEqual(closure.buffer_masters(model), ['bufbuf_16', 'clkbuf_16'])

    def test_missing_buffer_models_fail_before_reset_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / 'ss.lib'
            model.write_text('library("ss") {}')
            with self.assertRaisesRegex(RuntimeError, 'No noninverting buffer masters'):
                closure.buffer_masters(model)

    def test_stale_extraction_is_rejected_before_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            root = repo / 'hs'
            (root / 'reports_450').mkdir(parents=True)
            spef = root / 'route.max.normalized.spef'
            spef.write_text('original')
            report = {'sha256': {'hs/route.max.normalized.spef': closure.sha(spef)}, 'model_sha256': {}}
            (root / 'reports_450/assessment.json').write_text(json.dumps(report))
            with patch.object(closure, 'REPO', repo):
                self.assertEqual(closure.current_reports(root), report)
                spef.write_text('different geometry')
                with self.assertRaisesRegex(RuntimeError, 'Stale closure input'):
                    closure.current_reports(root)
            self.assertFalse((root / 'closure').exists())

    def test_checkpoint_preserves_geometry_and_rtl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'route.odb').write_bytes(b'database')
            (root / 'rtl_snapshot').mkdir()
            (root / 'rtl_snapshot/core.v').write_text('module core; endmodule')
            first = closure.archive(root)
            (root / 'route.odb').write_bytes(b'new database')
            second = closure.archive(root)
            self.assertNotEqual(first, second)
            self.assertEqual((first / 'input/route.odb').read_bytes(), b'database')
            self.assertEqual((first / 'input/rtl_snapshot/core.v').read_text(), 'module core; endmodule')
            manifest = json.loads((first / 'input_manifest.json').read_text())
            self.assertEqual(manifest['route.odb'], hashlib.sha256(b'database').hexdigest())

    def test_direct_receiver_connections_are_identified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = {'netnames': {'pipe': {'bits': [10, 11], 'attributes': {'ASYNC_REG': 'TRUE'}}},
                      'cells': {'first': {'connections': {'D': [1], 'Q': [10]}},
                                'second': {'connections': {'D': [10], 'Q': [11]}},
                                'consumer': {'connections': {'D': [11], 'Q': [12]}}}}
            (root / 'mapped.json').write_text(json.dumps({'modules': {'IntegerPLL_AcquiringCore': module}}))
            self.assertEqual(closure.protected_receivers(root), ['second/D'])


class EvidenceTests(unittest.TestCase):
    def test_local_clock_branches_must_have_clock_routing_role(self):
        module = {'cells': {'closure_cdc_clock_0': {}, 'closure_cdc_clock_1': {}, 'data_buffer': {}}}
        self.assertEqual(closure_audit.clock_role_failures(module,
                         'closure_cdc_clock_0_out CLOCK\nclosure_cdc_clock_1_out SIGNAL\n'), ['closure_cdc_clock_1_out'])
        self.assertEqual(closure_audit.clock_role_failures(module,
                         'closure_cdc_clock_0_out CLOCK\n'), ['closure_cdc_clock_1_out'])

    def test_equivalent_buffer_on_direct_receiver_link_is_rejected(self):
        mapped = {'netnames': {'pipe': {'bits': [10, 11], 'attributes': {'ASYNC_REG': 'TRUE'}}},
                  'cells': {'first': {'connections': {'CLK': [2], 'D': [1], 'Q': [10]}},
                            'second': {'connections': {'CLK': [2], 'D': [10], 'Q': [11]}}}}
        physical = {'cells': {'first': {'connections': {'D': [100], 'Q': [200]}},
                              'second': {'connections': {'D': [200], 'Q': [300]}}}}
        self.assertEqual(closure_audit.receiver_link_failures(mapped, physical), [])
        physical['cells']['second']['connections']['D'] = [201]
        self.assertEqual(closure_audit.receiver_link_failures(mapped, physical), ['second/D'])
        mapped['cells']['second']['connections']['CLK'] = [3]
        self.assertEqual(closure_audit.receiver_link_failures(mapped, physical), [])

    def test_receiver_pairs_exclude_cross_domain_meta_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = {'netnames': {'pipe': {'bits': [10, 11, 12], 'attributes': {'ASYNC_REG': 'TRUE'}}},
                      'cells': {'first': {'connections': {'CLK': [2], 'D': [1], 'Q': [10]}},
                                'second': {'connections': {'CLK': [2], 'D': [10], 'Q': [11]}},
                                'crossing': {'connections': {'CLK': [3], 'D': [11], 'Q': [12]}}}}
            (root / 'mapped.json').write_text(json.dumps({'modules': {'IntegerPLL_AcquiringCore': module}}))
            self.assertEqual(closure.receiver_pairs(root), [('first', 'second')])
            self.assertEqual(closure.protected_receivers(root), ['second/D'])

    def test_missing_corner_or_path_group_cannot_pass(self):
        result = {'models': dict.fromkeys(('ss', 'tt', 'ff'), 'model'),
                  'gates': {c.replace('_', '/'): True for c in closure.CORNERS},
                  'timing_ns': {cell: {rc: {f'{kind}/{group}': .3
                    for kind in ('max', 'min') for group in closure_audit.GROUPS}
                    for rc in ('min', 'nom', 'max')} for cell in ('ss', 'tt', 'ff')},
                  'diagnostic_timing_pass': True}
        self.assertTrue(closure_audit.valid_matrix(result))
        del result['timing_ns']['ss']['max']['min/asynchronous']
        self.assertFalse(closure_audit.valid_matrix(result))
        del result['gates']['ff/nom']
        self.assertFalse(closure_audit.valid_matrix(result))

    def test_unannotated_active_net_is_rejected(self):
        module = {'cells': {
            'driver': {'type': 'sky130_fd_sc_hs__buf_4', 'connections': {'X': [7]}, 'port_directions': {'X': 'output'}},
            'sink': {'type': 'sky130_fd_sc_hs__inv_1', 'connections': {'A': [7], 'Y': [8]}, 'port_directions': {'A': 'input', 'Y': 'output'}}},
            'ports': {}}
        text = 'Found 2 unannotated drivers.\n driver/X\n sink/Y\nSETUP_AND_RECOVERY_SCREEN'
        self.assertEqual(closure_audit.annotation_failures(module, text), ['driver/X'])

    def test_omitted_dummy_outputs_require_declared_output_direction(self):
        module = {'cells': {'dummy': {'type': 'inv', 'connections': {'A': [7]}, 'port_directions': {'A': 'input'}},
                            'tie': {'type': 'sky130_fd_sc_hs__conb_1', 'connections': {'HI': [8]}, 'port_directions': {'HI': 'output'}}},
                  'ports': {}}
        views = {'inv': {'ports': {'A': {'direction': 'input'}, 'Y': {'direction': 'output'}}}}
        text = 'Found 4 unannotated drivers.\n dummy/Y\n dummy/A\n tie/LO\n missing/Y\nSETUP_AND_RECOVERY_SCREEN'
        self.assertEqual(closure_audit.annotation_failures(module, text, views), ['dummy/A', 'missing/Y'])


if __name__ == '__main__':
    unittest.main()
