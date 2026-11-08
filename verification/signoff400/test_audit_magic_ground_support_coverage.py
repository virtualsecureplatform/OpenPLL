import unittest
from audit_magic_ground_support_coverage import coverage
class Coverage(unittest.TestCase):
    def args(self):
        inventory=[dict(file='ExtBasic.c',line=n,reset=False) for n in [5332,5351,5409,5459,5510,5560]]
        inventory += [dict(file='ExtCouple.c',line=n,reset=False) for n in [234,239,522,1254,1521,1703]]
        inventory += [dict(file=f,line=n,reset=True) for f,n in [('ExtBasic.c',336),('ExtBasic.c',5248),('ExtBasic.c',5568),('ExtCouple.c',1525),('ExtCouple.c',1707),('ExtRegion.c',403)]]
        observed={r['file']+':'+str(r['line']):2 for r in inventory}
        return [inventory,dict(mutation_sites_observed=observed),{r['file']+':'+str(r['line']):2 for r in inventory[:6]},dict(ground_overlap_subtractions=2),dict(ground_halo_subtractions=2),dict(halo_tail_events=2)]
    def test_coverage_preserves_explicit_unqualified_paths(self):
        r=coverage(*self.args());self.assertTrue(r['all_nine_supported_site_counts_match']);self.assertTrue(r['legacy_ground_path_observed']);self.assertFalse(r['pointwise_placement_qualified'])
    def test_missing_geometry_site_cannot_hide_in_total(self):
        a=self.args();a[2]['ExtBasic.c:5332']=1;a[2]['ExtBasic.c:5409']=3
        with self.assertRaisesRegex(ValueError,'coverage mismatch'):coverage(*a)
    def test_missing_subtraction_and_unknown_native_site_rejected(self):
        a=self.args();a[4]['ground_halo_subtractions']=1
        with self.assertRaisesRegex(ValueError,'coverage mismatch'):coverage(*a)
        a=self.args();a[1]['mutation_sites_observed']['unknown']=1
        with self.assertRaisesRegex(ValueError,'outside'):coverage(*a)
if __name__=='__main__':unittest.main()
