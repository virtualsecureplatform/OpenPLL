import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT, save


class NativeTileCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temp.name)/'catalog'
        subprocess.run(['g++', '-std=c++20', '-O2', str(ROOT/'tools/native_rc_coverage/catalog_native_tiles.cpp'),
                        '-o', str(cls.binary)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def tile(self, group, single=False):
        names = [f'_rmesh_{group}_a'] if single else [f'_rmesh_{group}_a', f'_rmesh_{group}_b']
        return dict(native_group_id=str(group), tile_serial=1, native_working_plane_id=10,
                    raw_type_id='98', raw_material='metal1', original_conductor='same label',
                    box_internal=[0, 0, 10, 2], split=0, private_voltage_nodes=names,
                    breakpoints=[dict(private_id=n, point_internal=[5, 1]) for n in names])

    def axis(self, tile):
        return dict(native_group_id=tile['native_group_id'], native_working_plane_id=10,
                    raw_type_id='98', raw_material='metal1', original_conductor='same label',
                    tile_box_internal=tile['box_internal'], preparation_state='native_full_axis_candidate',
                    geometric_axis_prepared=True, numeric_end_resistors_complete=True,
                    native_voltage_knots=[[0, tile['private_voltage_nodes'][0]], [10, tile['private_voltage_nodes'][-1]]],
                    runtime_model_eligible=False, release_qualified=False)

    def invoke(self, root, tiles, axes, deadline=None):
        for name, rows in [('tiles', tiles), ('axes', axes)]:
            (root/(name+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
        save(root/'config.json', dict(tiles=str(root/'tiles.jsonl'), axes=str(root/'axes.jsonl'),
            nominal_sheet_values={'metal1': '125'}, output=str(root/'native'),
            deadline_uptime=deadline or time.clock_gettime(time.CLOCK_BOOTTIME)+30))
        return subprocess.run([self.binary, root/'config.json'], capture_output=True, text=True)

    def test_all_tiles_axis_offsets_and_actual_anchor_cuts(self):
        tiles = [self.tile(1), self.tile(2, True), self.tile(3)]
        axes = [self.axis(tiles[0]), self.axis(tiles[2])]
        axes[1].update(preparation_state='deferred_zero_R_constraint', geometric_axis_prepared=False,
                       numeric_end_resistors_complete=False)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p = self.invoke(root, tiles, axes)
            self.assertEqual(p.returncode, 0, p.stderr)
            rows = [json.loads(line) for line in (root/'native/tile_catalog.jsonl').read_text().splitlines()]
            self.assertEqual([r['catalog_state'] for r in rows],
                             ['native_axis_candidate', 'anchored_sheet_candidate', 'deferred_native_axis'])
            self.assertEqual(rows[1]['base_x_cuts_internal'], [0, 5, 10])
            self.assertEqual(rows[1]['base_y_cuts_internal'], [0, 1, 2])
            self.assertFalse(rows[1]['runtime_model_eligible'])
            with (root/'axes.jsonl').open('rb') as f:
                for r in (rows[0], rows[2]):
                    f.seek(r['axis_registry_byte_offset'])
                    self.assertEqual(json.loads(f.readline()), axes[r['axis_registry_row']-1])
            summary = json.loads((root/'native/summary.json').read_text())
            self.assertEqual(summary['native_tiles'], 3)
            self.assertEqual(summary['parameterized_bases_prepared'], 2)

    def test_identity_ambiguity_missing_axis_and_cross_snapshot_rejected(self):
        for fault in ('missing', 'duplicate_axis', 'duplicate_tile', 'nodes', 'snapshot'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                tiles = [self.tile(1)]
                axes = [self.axis(tiles[0])]
                if fault == 'missing':
                    tiles.append(self.tile(2))
                elif fault == 'duplicate_axis':
                    axes.append(axes[0])
                elif fault == 'duplicate_tile':
                    tiles.append(tiles[0])
                elif fault == 'nodes':
                    axes[0]['native_voltage_knots'][1][1] = '_rmesh_1_other'
                else:
                    tiles[0]['private_voltage_nodes'][0] = '_rmesh_2_a'
                self.assertNotEqual(self.invoke(Path(temp), tiles, axes).returncode, 0)

    def test_outside_anchor_is_deferred_and_deadline_enforced(self):
        tile, axis_tile = self.tile(2, True), self.tile(1)
        tile['breakpoints'][0]['point_internal'] = [11, 1]
        for expired in (False, True):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                p = self.invoke(root, [axis_tile, tile], [self.axis(axis_tile)],
                    time.clock_gettime(time.CLOCK_BOOTTIME)-1 if expired else None)
                if expired:
                    self.assertNotEqual(p.returncode, 0)
                else:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    r = json.loads((root/'native/tile_catalog.jsonl').read_text().splitlines()[1])
                    self.assertEqual(r['catalog_state'], 'deferred_outside_anchor')
                    self.assertFalse(r['parameterized_basis_prepared'])
