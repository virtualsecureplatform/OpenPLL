import unittest
from assess_hs_timing_coverage import combine,interpolate


class EnvelopeControls(unittest.TestCase):
    def test_crossing_tables_are_bounded_between_knots(self):
        a=dict(index_1=[0,1],index_2=[0,1],values=[[1,2],[4,5]])
        b=dict(index_1=[0,.4,1],index_2=[0,.6,1],values=[[2,2.1,2.2],[2.4,2.5,2.6],[3,3.1,3.2]])
        low=combine([a,b],True);high=combine([a,b],False)
        for x in [.1,.25,.5,.8]:
            for y in [.1,.5,.75,.9]:
                for table in [a,b]:
                    actual=interpolate(table,(x,y))
                    self.assertLessEqual(interpolate(low,(x,y)),actual+1e-12)
                    self.assertGreaterEqual(interpolate(high,(x,y)),actual-1e-12)

    def test_common_domain_is_enforced(self):
        a=dict(index_1=[0,1],index_2=[0,1],values=[[1,2],[3,4]])
        b=dict(index_1=[.5,1.5],index_2=[.5,1.5],values=[[2,3],[4,5]])
        result=combine([a,b],False)
        self.assertEqual(result['index_1'],[.5,1])
        with self.assertRaises(AssertionError):interpolate(result,(.2,.7))

    def test_disjoint_domains_cannot_be_extrapolated(self):
        a=dict(index_1=[0,1],index_2=[0,1],values=[[1,2],[3,4]])
        b=dict(index_1=[2,3],index_2=[0,1],values=[[1,2],[3,4]])
        with self.assertRaises(ValueError):combine([a,b],True)


if __name__=='__main__':
    unittest.main()
