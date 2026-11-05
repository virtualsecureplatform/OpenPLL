import copy
from fractions import Fraction
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from common import ROOT, save, sha
from audit_native_tile_catalog import audit_row, run
import test_native_tile_catalog as producer


class NativeTileCatalogAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        producer.NativeTileCatalog.setUpClass()

    @classmethod
    def tearDownClass(cls):
        producer.NativeTileCatalog.tearDownClass()

    def fixture(self, root):
        p = producer.NativeTileCatalog()
        tiles = [p.tile(1), p.tile(2, True), p.tile(3)]
        axes = [p.axis(tiles[0]), p.axis(tiles[2])]
        axes[1].update(preparation_state='deferred_zero_R_constraint', geometric_axis_prepared=False,
                       numeric_end_resistors_complete=False)
        result = p.invoke(root, tiles, axes)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in (root/'native/tile_catalog.jsonl').read_text().splitlines()]
        return tiles, axes, rows

    def test_independent_rows_and_adversarial_descriptors(self):
        with tempfile.TemporaryDirectory() as temp:
            tiles, axes, rows = self.fixture(Path(temp))
            for n, (tile, row) in enumerate(zip(tiles, rows), 1):
                axis = None if n == 2 else axes[0 if n == 1 else 1]
                location = None if axis is None else (row['axis_registry_row'], row['axis_registry_byte_offset'])
                self.assertEqual(audit_row(tile, row, n, row['source_tile_byte_offset'],
                                          {'metal1': Fraction(125)}, axis, location), row['catalog_state'])
            for field, value in [('latent_node_namespace', 'wrong'), ('base_x_cuts_internal', [0, 10]),
                                 ('nominal_sheet_milliohms_per_square', '126'),
                                 ('physical_RC_qualified', True), ('source_tile_byte_offset', -1),
                                 ('parameterized_basis_prepared', False)]:
                r = copy.deepcopy(rows[1])
                r[field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    audit_row(tiles[1], r, 2, rows[1]['source_tile_byte_offset'], {'metal1': Fraction(125)})
            r = copy.deepcopy(rows[0])
            r['private_voltage_nodes'][0] = '_rmesh_2_a'
            with self.assertRaises(ValueError):
                audit_row(tiles[0], r, 1, 0, {'metal1': Fraction(125)}, axes[0], (1, 0))

    def receipt(self, root):
        source = root/'sources'
        (source/'native').mkdir(parents=True)
        shutil.copyfile(root/'tiles.jsonl', source/'tile_domains.jsonl')
        shutil.copyfile(root/'axes.jsonl', source/'native/axis_registry.jsonl')
        shutil.copyfile(ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech', source/'sky130A.tech')
        receipt = json.loads((root/'native/summary.json').read_text())
        receipt['input_sha256'] = {str(p): sha(p) for p in
            (source/'tile_domains.jsonl', source/'native/axis_registry.jsonl', source/'sky130A.tech')}
        receipt['artifacts'] = {str(root/'native/tile_catalog.jsonl'): sha(root/'native/tile_catalog.jsonl')}
        save(root/'assessment.json', receipt)

    def test_complete_stream_and_swapped_reference_rejection(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                _, _, rows = self.fixture(root)
                if corrupt:
                    rows[0]['axis_registry_byte_offset'] = rows[2]['axis_registry_byte_offset']
                    rows[0]['axis_registry_row'] = rows[2]['axis_registry_row']
                    (root/'native/tile_catalog.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                self.receipt(root)
                if corrupt:
                    with self.assertRaises(ValueError):
                        run(root, root/'audit')
                else:
                    result = run(root, root/'audit')
                    self.assertEqual(result['native_tiles'], 3)
                    self.assertEqual(result['axis_records_consumed_once'], 2)
                    self.assertFalse(result['physical_RC_qualified'])
