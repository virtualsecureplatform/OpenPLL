import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from zero_C_followup import trace_targets


class FollowupNamespaceControls(unittest.TestCase):
    def fixture(self,root):
        compact=root/'compact.bin';compact.write_bytes(b'CNETDOF1'+struct.pack('<QQ',5,4)+struct.pack('<5I',0,1,2,2,3))
        nodes=root/'nodes.jsonl';nodes.write_text('\n'.join(json.dumps(r) for r in [[1,'_rmesh_8_1'],[2,'_rmesh_7_2'],[3,'_rmesh_sheet_7_20:r1:1'],[4,'_rmesh_axis_end_8_21_lo']])+'\n')
        index=root/'index.bin';index.write_bytes(b'RBSIDX01'+struct.pack('<Q',4)+struct.pack('<QII',2**64-1,0,0)+
              struct.pack('<QII',0,1,0)+struct.pack('<QII',1,1,1)+struct.pack('<QII',2,1,2))
        bundles=root/'bundles.jsonl';bundles.write_text('\n'.join(json.dumps(r) for r in [
            dict(bundle_id=0,tile_references=[[0,0,'7',20]]),dict(bundle_id=1,tile_references=[[0,0,'8',21]]),
            dict(bundle_id=2,tile_references=[[0,0,'7',22]])])+'\n')
        return compact,nodes,index,bundles

    def test_every_alias_is_resolved_and_group_is_not_used_as_field_id(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.fixture(Path(folder));found=trace_targets([(2,'-3')],-70,*paths,4)
            self.assertEqual(found['global_fields'],[1,3])
            self.assertEqual([n['node'] for n in found['negative_nodes'][0]['original_voltage_nodes']],[2,3])
            self.assertTrue(all(n['candidate_global_fields']==[1,3] for n in found['negative_nodes'][0]['original_voltage_nodes']))

    def test_invalid_witnesses_and_incomplete_namespaces_rejected(self):
        for witnesses in ([],[(0,'-1')],[(4,'-1')],[(2,'0')],[(2,'1')],[(2,'-1'),(2,'-2')]):
            with self.subTest(witnesses=witnesses),tempfile.TemporaryDirectory() as folder:
                paths=self.fixture(Path(folder))
                with self.assertRaises(ValueError):trace_targets(witnesses,-70,*paths,4)
        for fault in ('missing_node','unknown_name','wrong_field_count'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as folder:
                paths=self.fixture(Path(folder));nodes=paths[1]
                if fault=='missing_node':nodes.write_text(json.dumps([2,'_rmesh_7_2'])+'\n')
                if fault=='unknown_name':nodes.write_text(nodes.read_text().replace('_rmesh_7_2','arbitrary_7_2'))
                with self.assertRaises(ValueError):trace_targets([(2,'-1')],-70,*paths,5 if fault=='wrong_field_count' else 4)


if __name__=='__main__':unittest.main()
