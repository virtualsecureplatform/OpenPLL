import copy
import json
from pathlib import Path
import tempfile
import unittest
from certify_sheet_shape_atlas import check_shape
from audit_unextracted_sheet_instances import audit_atlas


class AtlasAuditTest(unittest.TestCase):
    def fixture(self,root):
        atlas=root/'atlas';atlas.mkdir()
        request=dict(global_template_id=0,local_template_id='m1:0',coordinate_scale=5,
                     hull_gds_dbu=[[0,0],[10,0],[10,20],[0,20]],holes_gds_dbu=[],area_gds_dbu_squared=200,perimeter_gds_dbu=60)
        rows=check_shape(request)
        (atlas/'requests.json').write_text(json.dumps([request]))
        (atlas/'template_aliases.json').write_text(json.dumps([dict(local_template_id='m1:0',global_template_id=0)]))
        return rows

    def test_exact_saved_element_reconstruction_at_all_refinements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=self.fixture(root)
            (root/'atlas/templates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            _,_,sizes=audit_atlas(root,dict(exact_geometry_certificates=3))
            self.assertEqual([sizes[0,r] for r in (1,2,4)],[4,9,25])

    def test_rejects_corrupt_stiffness_mass_vertices_and_duplicate_variants(self):
        for case in ('stiffness','mass','vertices','duplicate'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);rows=self.fixture(root)
                if case=='stiffness':rows[0]['unit_sheet_stiffness'][0][2]='999'
                elif case=='mass':rows[0]['unit_area_mass'][0][2]='999'
                elif case=='vertices':rows[0]['points_native_internal'][1]=copy.deepcopy(rows[0]['points_native_internal'][0])
                else:rows[1]=copy.deepcopy(rows[0])
                (root/'atlas/templates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                with self.assertRaises(ValueError):audit_atlas(root,dict(exact_geometry_certificates=3))


if __name__=='__main__':unittest.main()
