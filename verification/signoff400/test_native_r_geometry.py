"""Creation points survive moved representative nodes and repeated snapshots."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import save,sha
from audit_r_geometry_v3 import SOURCE,run


def fixture(root):
    index=root/'index';index.mkdir();native=root/'R.log';segments=root/'S.log'
    n=['TYPE 1 "metal1"'];s=[];nodes=[];tiles=[]
    for group,x in ((1,0),(2,20)):
        gid=str(group);name='same conductor';a=f'_rmesh_{group}_1';b=f'_rmesh_{group}_2'
        n += [f'BEGIN {group} "{name}"',f'NODE {group} a "n0" {x+1} 4 0 0',f'NODE {group} b "n1" {x+9} 4 0 0',
              f'BRANCH {group} a r',f'EDGE {group} a a b 10 1 512',f'BRANCH {group} b r',f'EDGE {group} b a b 10 1 512',f'END {group}']
        s += [f'SEG r a b {x} 5 {x+10} 5 {x} 0 {x+10} 10 10 1 512 5 10',f'GROUP {group} "{name}"']
        nodes += [dict(private_id=a,native_pointer='a',original_conductor=name,printed_name='n0',point_internal=[x+1,4],native_group_id=gid),
                  dict(private_id=b,native_pointer='b',original_conductor=name,printed_name='n1',point_internal=[x+9,4],native_group_id=gid)]
        tiles += [dict(native_group_id=gid,original_conductor=name,raw_type_id='1',box_internal=[x,0,x+10,10],initial_breakpoint_count=2,
                       breakpoints=[dict(private_id=a,point_internal=[x,5]),dict(private_id=b,point_internal=[x+10,5])])]
    native.write_text('\n'.join(n)+'\n');segments.write_text('\n'.join(s)+'\n')
    save(index/'nodes.json',nodes);(index/'tile_domains.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in tiles))
    control=root/'domain';control.mkdir();save(control/'assessment.json',dict(native_rc_export_completed=True,
        artifacts={str(p):sha(p) for p in (native,segments)}))
    save(index/'assessment.json',dict(input_sha256={str(native):sha(native),str(control/'assessment.json'):sha(control/'assessment.json')},
        artifacts={str(p):sha(p) for p in (index/'nodes.json',index/'tile_domains.jsonl')},
        all_native_groups_and_snapshot_records_preserved=True,private_nodes=4,native_groups=2,domain_counts=dict(domains=2)))
    return index,native,segments


class NativeWireGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'audit'
        subprocess.run(['g++','-std=c++20','-O2',str(SOURCE),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def invoke(self,root,index,native,segments):
        cfg=root/'config.json';out=root/'native';save(cfg,dict(native=str(native),segments=str(segments),nodes=str(index/'nodes.json'),
            tiles=str(index/'tile_domains.jsonl'),output=str(out),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30))
        proc=subprocess.run([str(self.binary),str(cfg)],capture_output=True,text=True)
        return proc,out
    def test_reused_pointers_and_moved_representative_points_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index,native,segments=fixture(root);proc,out=self.invoke(root,index,native,segments)
            self.assertEqual(proc.returncode,0,proc.stderr);report=json.loads((out/'summary.json').read_text())
            self.assertEqual(report['native_nodes'],4);self.assertEqual(report['native_groups'],2)
            self.assertEqual(report['wire_branches'],2);self.assertEqual(report['wire_geometry_failures'],0)
            self.assertFalse(report['snapshot_selection_qualified']);self.assertFalse(report['runtime_model_eligible'])
    def test_changed_creation_value_tile_and_resolved_endpoint_are_nonpass(self):
        for fault in ('value','tile','endpoint'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);index,native,segments=fixture(root)
                if fault=='value':segments.write_text(segments.read_text().replace('10 1 512 5 10','11 1 512 5 10',1))
                else:
                    path=index/'tile_domains.jsonl';rows=[json.loads(l) for l in path.read_text().splitlines()]
                    if fault=='tile':rows[0]['box_internal'][2]=11
                    else:rows[0]['breakpoints'][1]['private_id']='_rmesh_1_1'
                    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
                proc,out=self.invoke(root,index,native,segments);self.assertEqual(proc.returncode,0,proc.stderr)
                self.assertEqual(json.loads((out/'summary.json').read_text())['wire_geometry_failures'],1)
    def test_zero_native_wire_is_counted_without_runtime_promotion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index,native,segments=fixture(root)
            native.write_text(native.read_text().replace('10 1 512','0 1 512'))
            segments.write_text(segments.read_text().replace('10 1 512 5 10','0 1 512 5 10'))
            proc,out=self.invoke(root,index,native,segments);self.assertEqual(proc.returncode,0,proc.stderr)
            result=json.loads((out/'summary.json').read_text())
            self.assertEqual(result['zero_wire_branches'],2)
            self.assertTrue(result['all_wire_creation_geometry_matched'])
            self.assertFalse(result['zero_resistance_model_qualified'])

    def test_creation_identity_does_not_qualify_unsupported_interpolation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index,native,segments=fixture(root)
            path=index/'tile_domains.jsonl';rows=[json.loads(l) for l in path.read_text().splitlines()]
            rows[0]['box_internal'][2]=9;path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            segments.write_text(segments.read_text().replace('0 0 10 10 10 1 512','0 0 9 10 10 1 512',1))
            proc,out=self.invoke(root,index,native,segments);self.assertEqual(proc.returncode,0,proc.stderr)
            result=json.loads((out/'summary.json').read_text())
            self.assertTrue(result['all_branch_creation_identities_matched'])
            self.assertFalse(result['all_wire_creation_geometry_matched'])
            self.assertEqual(result['failure_counts_by_material'],{'metal1':1})
            self.assertEqual(result['rectangular_interpolation_failures'],1)
            self.assertFalse(result['runtime_model_eligible'])

    def test_malformed_array_and_duplicated_incident_owner_rejected(self):
        for fault in ('array','owner'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);index,native,segments=fixture(root)
                if fault=='array':
                    path=index/'nodes.json';path.write_text(path.read_text().rstrip()[:-1]+',]\n')
                else:native.write_text(native.read_text().replace('BRANCH 1 b r\nEDGE 1 b','BRANCH 1 a r\nEDGE 1 a'))
                proc,_=self.invoke(root,index,native,segments);self.assertNotEqual(proc.returncode,0)
    def test_wrapper_pins_exact_native_domain_and_accounting(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index,native,segments=fixture(root)
            report=run(index,native,segments,root/'wrapped')
            self.assertTrue(report['all_wire_creation_geometry_matched'])
            self.assertEqual(report['native_tiles'],2)
            with segments.open('a') as stream:stream.write('changed\n')
            with self.assertRaisesRegex(ValueError,'native domain stream identity mismatch'):
                run(index,native,segments,root/'rejected')
