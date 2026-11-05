from pathlib import Path
import tempfile
import unittest
try:
    import pya
except ImportError:
    pya=None
@unittest.skipIf(pya is None,'requires pinned CAD image with KLayout')
class FloatingNonrectangles(unittest.TestCase):
    def test_hole_contours_and_field_identity_are_preserved(self):
        from capture_floating_nonrectangles import capture_polygon
        from floating_sheet_basis import mesh,certify
        layout=pya.Layout();cell=layout.create_cell('CONTROL');index=layout.layer(1,0)
        poly=pya.Polygon(pya.Box(0,0,300,300));poly.insert_hole([pya.Point(x,y) for x,y in [(100,100),(200,100),(200,200),(100,200)]])
        cell.shapes(index).insert(poly);row=dict(original_conductor='FLOAT',field_ids=[3,11],point_gds_dbu=[0,0],bbox_gds_dbu=[0,0,300,300],area_gds_dbu_squared=poly.area(),perimeter_gds_dbu=poly.perimeter())
        result=capture_polygon(cell,index,row);self.assertEqual(result['field_ids'],[3,11]);self.assertEqual(len(result['holes_gds_dbu']),1);self.assertTrue(result['all_edges_manhattan'])
        t=mesh(result['hull_gds_dbu'],result['holes_gds_dbu']);self.assertEqual(t['area'],poly.area());certify(t)
    def test_changed_area_rectangle_and_ambiguous_probe_rejected(self):
        from capture_floating_nonrectangles import capture_polygon
        for fault in ('area','rectangle','ambiguous'):
            with self.subTest(fault=fault):
                layout=pya.Layout();cell=layout.create_cell('CONTROL');index=layout.layer(1,0)
                poly=pya.Polygon([pya.Point(x,y) for x,y in [(0,0),(300,0),(300,100),(100,100),(100,300),(0,300)]]) if fault!='rectangle' else pya.Polygon(pya.Box(0,0,300,300))
                cell.shapes(index).insert(poly)
                if fault=='ambiguous':cell.shapes(index).insert(poly)
                row=dict(original_conductor='FLOAT',field_ids=[3],point_gds_dbu=[0,0],bbox_gds_dbu=[0,0,300,300],area_gds_dbu_squared=poly.area()+(1 if fault=='area' else 0),perimeter_gds_dbu=poly.perimeter())
                with self.assertRaises(ValueError):capture_polygon(cell,index,row)
