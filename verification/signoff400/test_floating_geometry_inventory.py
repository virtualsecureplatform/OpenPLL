import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT,save
class FloatingGeometryInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'inventory'
        subprocess.run(['g++','-std=c++20','-O2',str(ROOT/'tools/native_rc_coverage/floating_geometry.cpp'),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def invoke(self,root,ext):
        (root/'view.ext').write_text(ext)
        rows=[dict(field_id=i,field=[n,p,m],EXT_inventory_state='declared_component_without_port_device_or_native_R') for i,(n,p,m) in enumerate([('FLOAT','metal1','metal1'),('FLOAT','arithmetic','unlocated'),('POLY','active','poly')])]
        (root/'inventory.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        save(root/'cfg.json',dict(ext=str(root/'view.ext'),inventory=str(root/'inventory.jsonl'),output=str(root/'native'),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30))
        return subprocess.run([str(self.binary),str(root/'cfg.json')],capture_output=True,text=True)
    def test_exact_native_points_classes_and_field_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=self.invoke(root,'resistclasses 125 48200\nnode "FLOAT" 0 1.25 10 20 m1 200 60 0 0\nnode "POLY" 1 2 30 40 p 0 0 100 40\n');self.assertEqual(p.returncode,0,p.stderr)
            d=json.loads((root/'native/summary.json').read_text());self.assertEqual(d['unique_native_conductors'],2);self.assertEqual(d['unmatched_fields'],3);self.assertEqual(d['nodes_without_exactly_one_nonzero_resistance_class'],0)
            r=json.loads((root/'native/nodes_m1.jsonl').read_text());self.assertEqual(r['field_ids'],[0,1]);self.assertEqual(r['point_internal'],[10,20]);self.assertEqual(r['native_classes'][0]['native_sheet_class_value'],125)
    def test_missing_duplicate_and_truncated_nodes_rejected(self):
        for fault in ('missing','duplicate','truncated'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                ext='resistclasses 125\nnode "FLOAT" 0 1 10 20 m1 200 60\n'
                ext+= '' if fault=='missing' else 'node "FLOAT" 0 1 10 20 m1 200 60\n' if fault=='duplicate' else 'node "POLY" 0 1 1 1 p 100\n'
                root=Path(temp);self.assertNotEqual(self.invoke(root,ext).returncode,0);self.assertFalse((root/'native/summary.json').exists())
