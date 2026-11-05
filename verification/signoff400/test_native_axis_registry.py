import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT,save
class NativeAxisRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'prepare';subprocess.run(['g++','-std=c++20','-O2',str(ROOT/'tools/native_rc_coverage/prepare_axis_registry.cpp'),'-lgmpxx','-lgmp','-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def row(self,gid,lo,hi,material='metal1',resistance='10',state='uncovered_tile_ends'):
        return dict(native_group_id=str(gid),original_conductor='same label',native_working_plane_id=1,raw_material=material,raw_type_id='1',tile_box_internal=[0,0,10,2],flow_axis=0,state=state,segments=[[lo,hi,f'_rmesh_{gid}_a',f'_rmesh_{gid}_b',resistance,'reused pointer']])
    def invoke(self,root,rows):
        source=root/'chains.jsonl';source.write_text(''.join(json.dumps(r)+'\n' for r in rows));save(root/'cfg.json',dict(chains=str(source),nominal_sheet_values=dict(metal1='125'),output=str(root/'native'),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30));return subprocess.run([str(self.binary),str(root/'cfg.json')],capture_output=True,text=True)
    def test_complete_nominal_symbolic_and_deferred_states_are_all_retained(self):
        rows=[self.row(1,0,10,state='full_tile_chain_positive_R'),self.row(2,2,8),self.row(3,2,8,material='ndiff'),self.row(4,2,8,material='ndiode',resistance='0'),self.row(5,-1,10,state='unsupported_creation_geometry')]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=self.invoke(root,rows);self.assertEqual(p.returncode,0,p.stderr);out=[json.loads(s) for s in (root/'native/axis_registry.jsonl').read_text().splitlines()];summary=json.loads((root/'native/summary.json').read_text());self.assertEqual(summary['source_chains'],5);self.assertEqual(summary['native_segments_referenced'],5);self.assertEqual(summary['geometric_axes_prepared'],3)
            self.assertEqual(out[1]['end_stub_resistors'][0]['nominal_resistance_milliohms_exact'],['125','1']);self.assertEqual(out[1]['candidate_voltage_knots'][0][0],0);self.assertEqual(out[1]['candidate_voltage_knots'][-1][0],10)
            self.assertNotIn('nominal_resistance_milliohms_exact',out[2]['end_stub_resistors'][0]);self.assertFalse(out[2]['numeric_end_resistors_complete']);self.assertFalse(out[3]['geometric_axis_prepared']);self.assertFalse(out[4]['geometric_axis_prepared']);self.assertFalse(summary['runtime_model_eligible'])
            with (root/'chains.jsonl').open('rb') as f:
                for original,r in zip(rows,out):f.seek(r['source_chain_byte_offset']);self.assertEqual(json.loads(f.readline()),original)
    def test_explicit_aliases_survive_and_generated_states_do_not_collide(self):
        r=self.row(1,2,8);r['segments']=[[2,5,'_rmesh_1_a','_rmesh_1_b','1','p'],[5,8,'_rmesh_1_b','_rmesh_1_a','2','q']]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=self.invoke(root,[r]);self.assertEqual(p.returncode,0,p.stderr);out=json.loads((root/'native/axis_registry.jsonl').read_text());self.assertEqual([n for x,n in out['candidate_voltage_knots']][1:-1],['_rmesh_1_a','_rmesh_1_b','_rmesh_1_a']);self.assertEqual(len(out['end_stub_resistors']),2)
    def test_cross_snapshot_identity_and_negative_native_R_are_rejected(self):
        for fault in ('identity','resistance'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                r=self.row(1,2,8)
                if fault=='identity':r['segments'][0][3]='_rmesh_2_b'
                else:r['segments'][0][4]='-1'
                self.assertNotEqual(self.invoke(Path(temp),[r]).returncode,0)
