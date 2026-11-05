import unittest
from selected_publication_delivery import deliver
from fit_selected_publication_model import parameters,merge

class PublicationDeliveryTest(unittest.TestCase):
    def test_reset_zero_direction_selection_preserves_pulse_widths(self):
        p={'up':{'rise':{'nominal_ns':.466},'fall':{'nominal_ns':.455}}}
        edges,predicted=deliver('up',[(20,1),(40,0),(60,1),(80,0)],p)
        self.assertEqual(edges,[(20.466,1),(40.466,0),(60.455,1),(80.455,0)])
        self.assertEqual([r['Q_edge'] for r in predicted],['rise','fall'])

    def test_unmeasured_direction_cannot_reuse_rising_delay(self):
        p=parameters([dict(role='up',Q_edge='rise',latency_ns=.466)])
        self.assertNotIn('fall',p['up']);self.assertEqual(p['dn'],{})
        with self.assertRaisesRegex(ValueError,'needs_native_publication_direction'):
            deliver('up',[(20,1),(40,0),(60,1)],p)

    def test_empty_role_needs_no_artificial_events_and_identity_conflicts_reject(self):
        self.assertEqual(deliver('dn',[],{}),([],[]))
        with self.assertRaises(ValueError):merge({'a':'old'},{'a':'new'})

if __name__=='__main__':unittest.main()
