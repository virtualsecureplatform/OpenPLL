"""Contact attribution cannot move creation points or promote a voltage basis."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import save,sha
from test_native_r_geometry import fixture as base_fixture
from audit_r_geometry_v5 import SOURCE,run


def fixture(root,kind='overlap',outside=True):
    index,native,segments=base_fixture(root)
    path=index/'tile_domains.jsonl';tiles=[json.loads(line) for line in path.read_text().splitlines()]
    for tile in tiles:tile['native_working_plane_id']=3
    if outside:
        tiles[0]['box_internal'][2]=9
        segments.write_text(segments.read_text().replace('0 0 10 10 10 1 512','0 0 9 10 10 1 512',1))
    path.write_text(''.join(json.dumps(r)+'\n' for r in tiles))
    box={'overlap':[8,4,12,6],'touch':[9,4,11,6],'disjoint':[10,4,12,6]}.get(kind,[8,4,12,6])
    center=[10,5] if kind!='moved' else [11,5]
    rows=[dict(native_group_id='1',original_conductor='same conductor',private_id='_rmesh_1_2',
        center_internal=center,contact_rectangle_internal=box,native_working_plane_id=4 if kind=='other' else 3,
        contact_material='via',tile_pointer='t')]
    if kind=='missing':rows=[]
    contacts=index/'contact_domains.jsonl';contacts.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    proof=json.loads((index/'assessment.json').read_text())
    proof['contact_plane_records']=len(rows)
    proof['artifacts'].update({str(p):sha(p) for p in (path,contacts)})
    control=root/'domain/assessment.json';report=json.loads(control.read_text());report['artifacts'][str(segments)]=sha(segments);save(control,report)
    proof['input_sha256'][str(control)]=sha(control);save(index/'assessment.json',proof)
    return index,native,segments


class NativeBranchRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'audit'
        subprocess.run(['g++','-std=c++20','-O2',str(SOURCE),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def invoke(self,root,index,native,segments):
        config=root/'config.json';out=root/'native'
        save(config,dict(native=str(native),segments=str(segments),nodes=str(index/'nodes.json'),
            tiles=str(index/'tile_domains.jsonl'),contacts=str(index/'contact_domains.jsonl'),output=str(out),
            deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30))
        result=subprocess.run([str(self.binary),str(config)],capture_output=True,text=True)
        return result,out

    def test_contact_plane_overlap_touch_disjoint_and_missing_centers(self):
        categories=dict(overlap='same_plane_contact_center_overlaps_tile',touch='same_plane_contact_center_touches_tile',
            disjoint='same_plane_contact_center_disjoint_tile',other='contact_center_other_plane_only',
            moved='no_contact_center_match',missing='no_contact_center_match')
        for kind,expected in categories.items():
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);args=fixture(root,kind);process,out=self.invoke(root,*args)
                self.assertEqual(process.returncode,0,process.stderr)
                report=json.loads((out/'summary.json').read_text())
                self.assertEqual(report['outside_endpoint_classes'],{expected:1})
                self.assertEqual(report['rectangular_interpolation_failures'],1)
                self.assertFalse(report['outside_axis_voltage_basis_qualified'])
                self.assertFalse(report['runtime_model_eligible'])

    def test_reversed_resistor_endpoints_still_use_exact_creation_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index,native,segments=fixture(root)
            text=native.read_text().replace('EDGE 1 a a b','EDGE 1 a b a').replace('EDGE 1 b a b','EDGE 1 b b a');native.write_text(text)
            process,out=self.invoke(root,index,native,segments);self.assertEqual(process.returncode,0,process.stderr)
            row=json.loads((out/'outside_endpoints.jsonl').read_text())
            self.assertEqual(row['private_id'],'_rmesh_1_2');self.assertEqual(row['creation_point'],[10,5])
            self.assertEqual(row['resolved_node_point'],[9,4]);self.assertEqual(row['outside_distance_internal'],1)

    def test_unbound_contact_private_node_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index,native,segments=fixture(root)
            p=index/'contact_domains.jsonl';p.write_text(p.read_text().replace('_rmesh_1_2','_rmesh_1_99'))
            process,_=self.invoke(root,index,native,segments);self.assertNotEqual(process.returncode,0)

    def test_inside_points_leave_the_original_geometry_counts_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=fixture(root,outside=False);process,out=self.invoke(root,*args)
            self.assertEqual(process.returncode,0,process.stderr);report=json.loads((out/'summary.json').read_text())
            self.assertEqual(report['wire_branches'],2);self.assertEqual(report['outside_endpoint_count'],0)
            self.assertTrue(report['all_wire_creation_geometry_matched']);self.assertFalse(report['runtime_model_eligible'])

    def test_wrapper_verifies_contact_artifacts_and_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index,native,segments=fixture(root)
            report=run(index,native,segments,root/'wrapped')
            self.assertEqual(report['indexed_contact_plane_records'],1)
            self.assertEqual(report['wire_geometry_failures'],1)
            with (index/'contact_domains.jsonl').open('a') as stream:stream.write('changed\n')
            with self.assertRaisesRegex(ValueError,'indexed geometry artifact identity mismatch'):
                run(index,native,segments,root/'rejected')




    def test_all_branches_and_outside_creation_records_are_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);index,native,segments=fixture(root)
            text=native.read_text().replace('END 1\n','BRANCH 1 a c\nEDGE 1 a a b 5 1 0\nBRANCH 1 b c\nEDGE 1 b a b 5 1 0\nEND 1\n')
            native.write_text(text);proc,out=self.invoke(root,index,native,segments);self.assertEqual(proc.returncode,0,proc.stderr)
            summary=json.loads((out/'summary.json').read_text());self.assertEqual(summary['native_branch_records_emitted'],3);self.assertEqual(summary['wire_creation_records_emitted'],2);self.assertTrue(summary['all_native_branch_records_emitted']);self.assertEqual(summary['wire_geometry_failures'],1)
            raw=[json.loads(s) for s in (out/'native_branch_records.jsonl').read_text().splitlines()];self.assertEqual(sum(r['branch_kind']=='contact' for r in raw),1)
            wires=[json.loads(s) for s in (out/'wire_creation_records.jsonl').read_text().splitlines()];self.assertEqual(wires[0]['creation_private_ids'],['_rmesh_1_1','_rmesh_1_2']);self.assertFalse(wires[0]['creation_axis_inside_tile']);self.assertEqual(wires[0]['creation_points_internal'],[[0,5],[10,5]]);self.assertEqual(wires[0]['resolved_node_points_internal'],[[1,4],[9,4]]);self.assertFalse(wires[0]['voltage_basis_qualified'])
