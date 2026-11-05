import contextlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import save,sha
import inventory_small_C_rows as inventory


class SmallRowSelectionControls(unittest.TestCase):
    def test_exact_selection_excludes_reference_masked_and_isolated_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);candidate=root/'candidate';candidate.mkdir();rows=candidate/'rows.jsonl'
            # At quantum 2^-30, the 1e-8 threshold lies strictly between integers 10 and 11.
            values=[(1,1,False),(10,2,False),(0,0,False),(8,0,True),(11,3,False),(5,5,False)]
            rows.write_text(''.join(json.dumps(dict(row=i,L1_integer=str(l1),conservative_diagonal_integer=str(d),
                source_proven_zero_row=masked))+'\n' for i,(l1,d,masked) in enumerate(values)))
            manifest=candidate/'operator.json';save(manifest,dict(node_count=6,correction_certificate=dict(path=str(rows),
                 sha256=sha(rows),binary_quantum_exponent=-30)))
            save(candidate/'assessment.json',dict(conservative_C_stored_coefficient_derivative_certified=True,
                 logical_operator_manifest=str(manifest),artifacts={str(manifest):sha(manifest)}))
            # No native work: the temporary fixture covers only deterministic selection and receipt semantics.
            with patch.object(inventory,'lease',return_value=contextlib.nullcontext()):inventory.run(candidate,root/'result')
            selected=json.loads((root/'result/candidates.json').read_text())
            self.assertEqual([r['row'] for r in selected['rows']],[1,5])
            self.assertFalse(selected['coefficient_change_authorized'])
            a=json.loads((root/'result/assessment.json').read_text())
            self.assertEqual(a['original_exact_zero_L1_rows'],1)
            self.assertEqual(a['already_source_proven_zero_rows'],1)
            self.assertFalse(a['source_level_zero_row_certificate_complete'])
            self.assertFalse(a['full_matrix_passivity_verified'])


if __name__=='__main__':unittest.main()
