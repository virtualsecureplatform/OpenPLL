import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT,save
class WireChainInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'inventory';subprocess.run(['g++','-std=c++20','-O2',str(ROOT/'tools/native_rc_coverage/classify_wire_chains.cpp'),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def row(self,group,lo,hi,a,b,value=1.,box=None):
        return dict(native_group_id=str(group),original_conductor='same label',flow_axis=0,creation_tile_internal=box or [0,0,10,2],creation_points_internal=[[lo,1],[hi,1]],creation_private_ids=[f'_rmesh_{group}_{a}',f'_rmesh_{group}_{b}'],native_resistance_value=value,native_resistance_text=str(value),native_branch_pointer=f'{lo}:{hi}',split_tile=False,width_internal=2,centerline_internal=1,native_working_plane_id=1,raw_material='metal1',raw_type_id='m1')
    def invoke(self,root,rows):
        p=root/'wires.jsonl';p.write_text(''.join(json.dumps(r)+'\n' for r in rows));cfg=root/'cfg.json';save(cfg,dict(wires=str(p),output=str(root/'native'),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30));return subprocess.run([str(self.binary),str(cfg)],capture_output=True,text=True)
    def test_full_uncovered_gapped_zero_and_repeated_labels(self):
        rows=[self.row(1,0,4,'a','b'),self.row(1,4,10,'b','c'),self.row(2,1,9,'a','b'),self.row(3,0,4,'a','b'),self.row(3,6,10,'c','d'),self.row(4,0,10,'a','b',0.)]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=self.invoke(root,rows);self.assertEqual(p.returncode,0,p.stderr);r=json.loads((root/'native/summary.json').read_text());self.assertEqual(r['wire_segments'],6);self.assertEqual(r['tile_axis_chains'],4)
            self.assertEqual(r['chains_by_state'],dict(full_tile_chain_positive_R=1,uncovered_tile_ends=1,not_one_continuous_axis_chain=1,full_tile_chain_with_zero_R=1));self.assertFalse(r['complete_voltage_basis_qualified'])
            out=[json.loads(s) for s in (root/'native/chains.jsonl').read_text().splitlines()];self.assertEqual(out[1]['uncovered_axis_ends_internal'],[1,1]);self.assertEqual(len(out[0]['segments']),2)
    def test_outside_overlap_and_node_discontinuity_stay_nonpassing(self):
        for fault in ('outside','overlap','identity'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                rows=[self.row(1,0,4,'a','b'),self.row(1,4,10,'b','c')]
                if fault=='outside':rows[0]['creation_points_internal'][0][0]=-1
                if fault=='overlap':rows[1]['creation_points_internal'][0][0]=3
                if fault=='identity':rows[1]['creation_private_ids'][0]='_rmesh_1_different'
                root=Path(temp);p=self.invoke(root,rows);self.assertEqual(p.returncode,0,p.stderr);r=json.loads((root/'native/summary.json').read_text());self.assertNotIn('full_tile_chain_positive_R',r['chains_by_state'])
    def test_cross_snapshot_private_identity_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            row=self.row(1,0,10,'a','b');row['creation_private_ids'][1]='_rmesh_2_b';self.assertNotEqual(self.invoke(Path(temp),[row]).returncode,0)
