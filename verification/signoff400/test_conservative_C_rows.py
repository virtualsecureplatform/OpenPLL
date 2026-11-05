import json
from pathlib import Path
import tempfile
import time
import unittest
from audit_conservative_C_rows import audit_rows


class ExactRowReplayControls(unittest.TestCase):
    def test_signed_indefinite_energy_witnesses_and_consistent_positive_rows(self):
        base=Path(__file__).resolve().parents[2]/'build/signoff400/conservative_C_controls_001'
        for name,expected in (('signed_indefinite',2),('cancelled',0),('zero',0)):
            path=base/name/'certify_conservative_C.rows.jsonl'
            count=len(path.read_text().splitlines())
            found=audit_rows(path,count,time.clock_gettime(time.CLOCK_BOOTTIME)+60)
            self.assertEqual(found['negative_conservative_diagonals'],expected)
            self.assertFalse(found['full_matrix_passivity_verified'])
            for witness in found['negative_energy_witnesses']:self.assertLess(int(witness['energy_integer']),0)

    def test_inconsistent_corrections_and_truncated_coverage_are_rejected(self):
        row=dict(row=0,stored_diagonal_integer='2',residual_integer='1',L1_integer='3',
                 diagonal_correction_integer='-1',conservative_diagonal_integer='1')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'rows.jsonl'
            for field,value in (('row',1),('row',True),('diagonal_correction_integer','0'),
                                ('conservative_diagonal_integer','2'),('L1_integer','0')):
                path.write_text(json.dumps(dict(row,**{field:value}))+'\n')
                with self.subTest(field=field),self.assertRaises(ValueError):
                    audit_rows(path,1,time.clock_gettime(time.CLOCK_BOOTTIME)+60)
            path.write_text(json.dumps(row)+'\n')
            with self.assertRaises(ValueError):audit_rows(path,2,time.clock_gettime(time.CLOCK_BOOTTIME)+60)


if __name__=='__main__':unittest.main()
