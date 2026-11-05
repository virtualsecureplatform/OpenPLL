import unittest
from audit_prototype_final_campaign_coverage_v3 import merge_pins


class LineageMergeTests(unittest.TestCase):
    def test_shared_input_verified_once_without_dropping_unique_artifacts(self):
        pins={}
        for path in ('wave1','wave2'):
            merge_pins(pins,dict(input_sha256={'image':'a'*64},artifacts={path:'b'*64}))
        self.assertEqual(set(pins),{'image','wave1','wave2'})

    def test_conflict_between_native_receipts_is_rejected(self):
        pins={'image':'a'*64}
        with self.assertRaisesRegex(ValueError,'conflicting native lineage'):
            merge_pins(pins,dict(input_sha256={'image':'b'*64},artifacts={}))

    def test_artifact_cannot_shadow_a_different_input_digest(self):
        with self.assertRaisesRegex(ValueError,'conflicting native lineage'):
            merge_pins({},dict(input_sha256={'model':'a'*64},artifacts={'model':'b'*64}))


if __name__=='__main__':unittest.main()
