import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT,save
class RCExtInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'classify'
        subprocess.run(['g++','-std=c++20','-O2',str(ROOT/'tools/native_rc_coverage/classify_ext.cpp'),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_explicit_aliases_ports_devices_and_unresolved_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ext=root/'view.ext';ext.write_text('node "R" 0 1 0 0 m1\nnode "FLOAT" 0 1 2 2 m2\nnode "PORT" 0 1 3 3 m2\nnode "DEV" 0 1 4 4 m1\nequiv "A" "B"\nequiv "B" "R"\nport "PORT" 1 0 0 1 1 m2\ndevice mos model 0 0 1 1 "DEV" 0\n')
            groups=root/'groups.jsonl';groups.write_text(json.dumps(dict(original_conductor='R'))+'\n')
            names=['@SUBSTRATE_REFERENCE','A','FLOAT','PORT','DEV','MISSING'];inv=root/'fields.jsonl';inv.write_text(''.join(json.dumps(dict(field_id=i,field=[n,'metal1','metal1']))+'\n' for i,n in enumerate(names)))
            cfg=root/'cfg.json';save(cfg,dict(ext=str(ext),groups=str(groups),inventory=str(inv),output=str(root/'native'),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30))
            p=subprocess.run([str(self.binary),str(cfg)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
            d=json.loads((root/'native/summary.json').read_text());self.assertEqual(d['fields'],6);self.assertEqual(d['explicit_equivalence_records'],2);self.assertTrue(all(v==1 for v in d['counts'].values()));self.assertFalse(d['physical_domain_complete'])
