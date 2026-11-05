"""Native snapshots sharing a conductor label must not overwrite one another."""
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

import index_filled_domain_v4 as indexer


class FilledDomainGroups(unittest.TestCase):
    def run_fixture(self, root, truncate=False):
        domain = root / 'domain'
        trace = domain / 'trace'
        trace.mkdir(parents=True)
        owner = domain / 'owner.json'
        owner.write_text(json.dumps({'started_utc': datetime.now(timezone.utc).isoformat()}))
        (domain / 'assessment.json').write_text(json.dumps({
            'native_rc_export_completed': True, 'input_sha256': {}, 'artifacts': {}}))
        provenance = ['TYPE 2 "metal"']
        rows = []
        for group in (1, 2):
            # Native pointers can be reused after the GROUP snapshot.
            provenance += [f'BEGIN {group} "SAME_CONDUCTOR"',
                           f'NODE {group} ptr "N{group}" 0 0 0 0', f'END {group}']
            rows += ['ALLOC ptr', f'TILE {group} tile 1 2 0 0 0 2 2 1',
                     f'TBP {group} ptr 0 0',
                     'CONTACT contact ptr 0 1 2 1 tile 2 0 0 0 0 2 2',
                     'BIND dev 0 0 2 model 1 ptr',
                     'SINGLE ptr 0 0 2 2 2 0', f'GROUP {group} "SAME_CONDUCTOR"']
        if truncate:
            rows.pop()
        (trace / 'R_provenance.log').write_text('\n'.join(provenance) + '\n')
        (trace / 'R_bindings.log').write_text('\n'.join(rows) + '\n')
        planes = root / 'build/timing400/release_001/DCO_C_surface_trace_controls_001/nom_trace/surfaces.log'
        planes.parent.mkdir(parents=True)
        planes.write_text('TYPE 2 "metal"\nPLANE 1 "metal"\n')
        helper = root / 'verification/timing400/inspect_DCO_retained_R_mesh_geometry.py'
        helper.parent.mkdir(parents=True)
        helper.write_text('# fixture dependency\n')
        out = root / 'index'
        argv = ['indexer', '--domain', str(domain), '--output', str(out),
                '--original-owner', str(owner)]
        try:
            with patch.object(indexer, 'ROOT', root), patch.object(indexer, 'update_root'), patch.object(sys, 'argv', argv):
                indexer.main()
        finally:
            signal.alarm(0)
        return out

    def test_repeated_names_and_reused_pointers_preserve_every_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            out = self.run_fixture(Path(temp))
            report = json.loads((out / 'assessment.json').read_text())
            self.assertEqual(report['native_groups'], 2)
            self.assertEqual(report['original_conductors'], 1)
            self.assertTrue(report['all_native_groups_and_snapshot_records_preserved'])
            for name in ('nodes.json', 'device_bindings.json', 'single_breakpoint_tiles.json'):
                rows = json.loads((out / name).read_text())
                self.assertEqual(len(rows), 2)
                self.assertEqual({r['native_group_id'] for r in rows}, {'1', '2'})
            for name in ('tile_domains.jsonl', 'contact_domains.jsonl'):
                rows = [json.loads(r) for r in (out / name).read_text().splitlines()]
                self.assertEqual(len(rows), 2)
                self.assertEqual({r['native_group_id'] for r in rows}, {'1', '2'})
            nodes = json.loads((out / 'nodes.json').read_text())
            self.assertEqual(len({n['private_id'] for n in nodes}), 2)
            self.assertFalse(report['runtime_model_eligible'])

    def test_unclosed_snapshot_never_emits_assessment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(AssertionError):
                self.run_fixture(root, truncate=True)
            self.assertFalse((root / 'index/assessment.json').exists())


if __name__ == '__main__':
    unittest.main()
