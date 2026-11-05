import tempfile,unittest
from pathlib import Path
from assess_selected_detector_prefix import read_prefix,complete_cycles


class DetectorPrefixTest(unittest.TestCase):
    def raw(self,values):
        p=Path(self.temp.name)/'probe.raw'
        p.write_text('No. Variables: 3\nNo. Points:          \nVariables:\n0 time time\n1 V(A) voltage\n2 V(B) voltage\nValues:\n'+values)
        return p

    def setUp(self):self.temp=tempfile.TemporaryDirectory()
    def tearDown(self):self.temp.cleanup()

    def test_discard_partial_and_preserve_rounded_times(self):
        p=self.raw('0 0\n0\n0\n1 1e-9\n.5\n.2\n2 1e-9\n1.2\n.3\n3 2e-9\n1.8\n')
        rows,info=read_prefix(p,{'a':'A'})
        self.assertEqual(rows,[[0,0],[1e-9,.5],[1e-9,1.2]])
        self.assertTrue(info['incomplete_final_sample_discarded'])
        self.assertEqual(info['repeated_printed_timestamps'],1)

    def test_reject_nonfinite_unselected_voltage(self):
        with self.assertRaisesRegex(ValueError,'nonfinite'):
            read_prefix(self.raw('0 0\n0\nnan\n'),{'a':'A'})

    def test_reject_backwards_time(self):
        with self.assertRaisesRegex(ValueError,'order'):
            read_prefix(self.raw('0 0\n0\n0\n1 2e-9\n0\n0\n2 1e-9\n0\n0\n'),{'a':'A'})

    def test_only_full_capture_windows_count(self):
        names=['time_s','reference_pin','feedback_pin','detector_up','detector_dn','event_up','event_dn']
        rows=[[0,0,0,0,0,0,0],[20e-9,1.8,1.8,1.8,0,0,0],[21e-9,1.8,1.8,1.8,0,1.8,0],[25e-9,0,0,0,0,1.8,0]]
        mapping={'up':'event_up','dn':'event_dn'}
        self.assertEqual(complete_cycles(rows,names,mapping),[])
        rows.append([40e-9,0,0,0,0,1.8,0])
        cycles=complete_cycles(rows,names,mapping)
        self.assertEqual(len(cycles),1)
        self.assertEqual(cycles[0]['decision'],'up')
        self.assertTrue(cycles[0]['capture']['up']['one_toggle_per_detector_rise'])


if __name__=='__main__':unittest.main()
