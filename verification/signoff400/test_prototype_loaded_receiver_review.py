import unittest
from review_prototype_BBPD_with_sync import sync_metrics


def samples(glitch=False,missing=False):
    result=[]
    for t in (0,5,6,7,8,9,10,11,12,49,50,51,52,85,90):
        row=[t*1e-9]+[0.0]*9
        row[6]=1.8 if 10<=t<50 else 0
        row[8]=1.8 if not missing and 11<=t<51 else 0
        row[9]=1.8 if glitch and t==7 else 0
        result.append(tuple(row))
    return result


class LoadedReceiverReview(unittest.TestCase):
    def test_active_and_inactive_polarities_checked(self):
        result=sync_metrics(samples())
        self.assertTrue(all(r['one_delayed_capture_per_source_toggle_observed'] for r in result.values()))
        self.assertEqual(result['DN']['captured_events'],2)
        self.assertEqual(result['UP']['captured_events'],0)

    def test_false_capture_retained_even_if_output_recovers(self):
        result=sync_metrics(samples(glitch=True))['UP']
        self.assertFalse(result['one_delayed_capture_per_source_toggle_observed'])
        self.assertFalse(result['quiet_output_low_rail_screen_pass'])
        self.assertEqual(result['captured_events'],2)

    def test_missing_real_event_capture_rejected(self):
        self.assertFalse(sync_metrics(samples(missing=True))['DN']['one_delayed_capture_per_source_toggle_observed'])


if __name__=='__main__':unittest.main()
