import unittest,tempfile,json
from pathlib import Path
from partition_magic_ground_support_trace import partition
class Partition(unittest.TestCase):
    def run_partition(self,rows,check=None):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'source';out=p/'out';out.mkdir();source.write_text(''.join(json.dumps(r)+'\n' for r in rows));r=partition(source,out)
            if check:check(out)
            return r
    def test_pair_and_geometry_projections_preserve_order(self):
        rows=[dict(kind=k) for k in ['ground_halo_begin','fringe_rule_end','ground_halo_end','ground_halo_subtract','ground_update','ground_support','ground_update','overlap_support_end','ground_overlap_subtraction','ground_update','ground_halo_tail','ground_update']]
        def check(out):
            read=lambda n:[json.loads(x)['kind'] for x in (out/(n+'.jsonl')).read_text().splitlines()]
            self.assertEqual(read('ground_halo'),['ground_halo_begin','fringe_rule_end','ground_halo_end','ground_halo_subtract','ground_update'])
            self.assertEqual(read('numeric'),['ground_update']*4)
            self.assertEqual(read('ground_overlap'),['overlap_support_end','ground_overlap_subtraction','ground_update'])
        r=self.run_partition(rows,check);self.assertEqual(r['source_events'],12)
    def test_intervening_event_not_hidden_by_filter(self):
        with self.assertRaisesRegex(ValueError,'immediately'):self.run_partition([dict(kind='ground_support'),dict(kind='node_name'),dict(kind='ground_update')])
    def test_unknown_and_truncated_events_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown'):self.run_partition([dict(kind='unknown')])
        with self.assertRaisesRegex(ValueError,'truncated'):self.run_partition([dict(kind='ground_halo_tail')])
if __name__=='__main__':unittest.main()
