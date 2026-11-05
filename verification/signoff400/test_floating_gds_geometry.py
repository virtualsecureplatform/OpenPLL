import copy
import json
from pathlib import Path
import tempfile
import unittest
try:
    import pya
except ImportError:
    pya=None
@unittest.skipIf(pya is None,'requires pinned CAD image with KLayout')
class FloatingGDSGeometry(unittest.TestCase):
    def fixture(self,root,nonrectangle=False):
        lay=pya.Layout();lay.dbu=.001;top=lay.create_cell('CONTROL');li=lay.layer(68,20)
        if nonrectangle:top.shapes(li).insert(pya.Polygon([pya.Point(x,y) for x,y in [(100,200),(300,200),(300,250),(200,250),(200,300),(100,300)]]))
        else:top.shapes(li).insert(pya.Box(100,200,300,300))
        gds=root/'control.gds';lay.write(str(gds))
        row=dict(original_conductor='FLOAT',field_ids=[2,9],point_internal=[20,40],native_type='m1',native_classes=[dict(area_internal_squared=600 if nonrectangle else 800,perimeter_internal=120)],spatial_field_keys=[['metal1','metal1']])
        return gds,row
    def invoke(self,root,gds,rows,name='result'):
        from check_floating_gds_geometry import run
        f=root/(name+'.jsonl');f.write_text(''.join(json.dumps(r)+'\n' for r in rows));return run(gds,f,root/name,'m1')
    def test_exact_corner_probe_and_native_area_perimeter(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);gds,row=self.fixture(root);r=self.invoke(root,gds,[row]);self.assertTrue(r['geometry_inventory_matches_all_nodes']);self.assertFalse(r['finite_R_basis_qualified']);self.assertEqual(r['integer_coordinate_scale'],5)
    def test_area_probe_material_duplicate_and_nonrectangle_rejected(self):
        for fault in ('area','probe','material','duplicate','nonrectangle'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);gds,row=self.fixture(root,fault=='nonrectangle');rows=[row]
                if fault=='area':row['native_classes'][0]['area_internal_squared']+=1
                if fault=='probe':row['point_internal']=[0,0]
                if fault=='material':row['spatial_field_keys']=[['metal2','metal2']]
                if fault=='duplicate':second=copy.deepcopy(row);second['original_conductor']='OTHER';rows.append(second)
                self.assertFalse(self.invoke(root,gds,rows)['geometry_inventory_matches_all_nodes'])
