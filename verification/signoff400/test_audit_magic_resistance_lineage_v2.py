import json
import unittest
import test_audit_magic_resistance_lineage as fixtures
from audit_magic_resistance_lineage_v2 import audit


class ExtendedLineageTests(fixtures.LineageTests):
    def run_audit(self):
        self.trace.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        return audit(self.trace, self.ext)

    def test_topological_adjustment_preserves_continuity(self):
        self.rows[2].update(kind='res_area_adjust', source_hex=1.0.hex(), name='series_transfer')
        r = self.run_audit()
        self.assertTrue(r['exported_rnode_records_match'])
        self.assertEqual(r['topological_area_adjustments'], 1)

    def test_corrupt_topological_adjustment_rejected(self):
        self.rows[2].update(kind='res_area_adjust', source_hex=2.0.hex(), name='series_transfer')
        with self.assertRaisesRegex(ValueError, 'topological'):
            self.run_audit()


if __name__ == '__main__':
    unittest.main()
