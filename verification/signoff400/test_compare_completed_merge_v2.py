import json
from pathlib import Path
import tempfile
import unittest
from common import save
class CompareCompletedMergeV2(unittest.TestCase):
    def test_exact_outputs_and_one_bit_change_under_original_deadline(self):
        from test_native_charge import source_fixture
        from compile_native_charge import run as compile_native
        from benchmark_charge_merge import run as reference_merge
        from benchmark_charge_merge_buffered import run as candidate_merge
        from compare_completed_charge_merge_v2 import run as compare
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,_=source_fixture(root);compiled=root/'compiled';compile_native(source,compiled,workers=1,wall_limit_s=180)
            reference=root/'reference';candidate=root/'candidate';reference_merge(compiled,reference,memory_gib=4);candidate_merge(compiled,candidate,memory_gib=4,threads=2)
            r=compare(candidate,reference,root/'comparison');self.assertTrue(r['full_reference_numeric_comparison']);self.assertFalse(r['merge_rerun']);self.assertTrue(r['original_deadline_preserved']);self.assertFalse(r['runtime_model_eligible'])
            p=candidate/'collapsed_matrix_ledger.json';rows=json.loads(p.read_text());p.write_text(json.dumps(rows,indent=2))
            spaced=compare(candidate,reference,root/'spaced');self.assertEqual(spaced['comparisons']['collapsed_matrix_ledger.json']['comparison_method'],'strict_parsed_numeric_bits')
            rows[0][2]+=1.;save(p,rows)
            with self.assertRaisesRegex(RuntimeError,'compiled worker failed'):compare(candidate,reference,root/'changed')
            self.assertFalse((root/'changed/assessment.json').exists())
