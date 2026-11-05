import unittest
from prototype_BBPD_guard_v2 import measure
from test_prototype_BBPD_guard_review import fixture


class EndpointGuard(unittest.TestCase):
    def test_half_supply_endpoint_roundoff_does_not_invent_an_edge(self):
        rows=fixture(-100)
        last=list(rows[-1]);last[2]=.9-1e-10;rows[-1]=tuple(last)
        result=measure(rows,-100)
        self.assertTrue(result['full_input_guard_edges_verified'])
        self.assertEqual(len(result['measured_analysis_phase_ps']),2)

    def test_wrong_endpoint_and_missing_interior_edge_rejected(self):
        rows=fixture(-100);last=list(rows[-1]);last[2]=.8;rows[-1]=tuple(last)
        with self.assertRaises(ValueError):measure(rows,-100)
        rows=fixture(-1000)
        rows=[(*r[:2],0,*r[3:]) if r[0]>=88e-9 else r for r in rows]
        with self.assertRaises(ValueError):measure(rows,-1000)


if __name__=='__main__':unittest.main()
