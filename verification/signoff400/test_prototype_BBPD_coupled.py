import copy
import unittest
from run_prototype_BBPD_coupled_pilot import receiver_binding,capture_metrics,read_table


def mapping():
    return dict(boundaries=[dict(bit=b,aliases=[dict(name=n,index=i)]) for b,n,i in ((1,'BBPD',0),(2,'BBPD',1),(3,'track_pipe',1),(4,'core.gen_local_resets.fast_pipe',1))],
        event_outputs=[dict(bit=5,aliases=[dict(name='core.bbpd_dn_event_toggle',index=0)]),dict(bit=6,aliases=[dict(name='core.bbpd_up_event_toggle',index=0)])],
        interface=['n_'+str(i) for i in range(1,7)]+['VGND','VNB','VPB','VPWR'])


def rows():
    return [(t*1e-9,0,0,1.8,dn,0,q,0) for t,dn,q in ((0,0,0),(19,0,0),(20,1.8,0),(20.4,1.8,1.8),(21,0,1.8),(59,0,1.8),(60,1.8,1.8),(60.4,1.8,0),(61,0,0),(90,0,0))]


class CoupledObserverIntegrity(unittest.TestCase):
    def test_boundary_aliases_must_be_explicit_and_unambiguous(self):
        m=mapping();self.assertEqual(receiver_binding(m)['n_1'],'DN')
        bad=copy.deepcopy(m);bad['boundaries'][0]['aliases'][0]['name']='unknown'
        with self.assertRaises(ValueError):receiver_binding(bad)
        bad=copy.deepcopy(m);bad['event_outputs'][1]['aliases']=bad['event_outputs'][0]['aliases']
        with self.assertRaises(ValueError):receiver_binding(bad)

    def test_missed_and_spurious_toggle_events_are_observed(self):
        r=rows();m=capture_metrics(r)
        self.assertTrue(m['DN']['one_toggle_per_detector_rise_observed'])
        self.assertTrue(m['UP']['one_toggle_per_detector_rise_observed'])
        missed=[(*x[:6],0,x[7]) for x in r]
        self.assertFalse(capture_metrics(missed)['DN']['one_toggle_per_detector_rise_observed'])
        spurious=[(*x[:7],x[6]) for x in r]
        self.assertFalse(capture_metrics(spurious)['UP']['one_toggle_per_detector_rise_observed'])

    def test_complete_seven_channel_native_table_required(self):
        text='No. of Data Rows : 2\n0 0 0 0 0 0 0 0 0\n1 9e-8 0 0 0 0 0 0 0\n'
        self.assertEqual(len(read_table(text)),2)
        with self.assertRaises(ValueError):read_table(text.replace('9e-8','8e-8'))
        with self.assertRaises(ValueError):read_table(text.replace('1 9e-8','3 9e-8'))


if __name__=='__main__':unittest.main()
