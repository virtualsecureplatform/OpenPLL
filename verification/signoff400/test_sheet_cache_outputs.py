import copy
import math
import unittest
from verify_sheet_cache_outputs import validate_replicas
class SheetCacheOutputs(unittest.TestCase):
    def fixture(self):
        base=[dict(id='native:1',nodes=['a','b'],matrix=[[0,0,1.],[0,1,-.25],[1,0,-.25],[1,1,.5]])]
        return base,[dict(copy.deepcopy(base[0]),id='native:1:replica'+str(i)) for i in range(2)]
    def test_complete_replica_bits_are_preserved(self):
        base,rows=self.fixture();self.assertEqual(validate_replicas(base,rows,copies=2),2)
    def test_bit_changes_duplicate_missing_and_identity_changes_rejected(self):
        for fault in ('bit','duplicate','missing','identity'):
            with self.subTest(fault=fault):
                base,rows=self.fixture()
                if fault=='bit':rows[1]['matrix'][0][2]=math.nextafter(1.,math.inf)
                elif fault=='duplicate':rows[1]['id']=rows[0]['id']
                elif fault=='missing':rows.pop()
                else:rows[1]['nodes'][0]='wrong'
                with self.assertRaises(ValueError):validate_replicas(base,rows,copies=2)
