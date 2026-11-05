import unittest
from review_prototype_native_decision_path import review


def waveform():
    rows=[]
    for index in range(641):
        t=index/10
        rows.append([t*1e-9,0,0,0,1.8 if 4<=t<36 else 0,
                     1.8 if 16<=t<17 or 48<=t<49 else 0,
                     1.8 if 5<=t<37 else 0,1.8 if 16.5<=t<48.5 else 0])
    return rows


class NativeDecisionReviewTests(unittest.TestCase):
    def test_accounts_for_both_updates_and_both_captures(self):
        result=review(waveform())
        self.assertEqual([r['expected_value'] for r in result['captures']],[1,0])
        self.assertTrue(all(r['D_stable_before_clock_ns']>10 for r in result['captures']))
        self.assertTrue(all(abs(d-1)<1e-10 for d in result['source_Q_to_destination_D_delay_ns']))

    def test_missing_output_capture_or_truncated_wave_rejected(self):
        rows=waveform()
        for row in rows:
            if row[0]>40e-9:row[7]=1.8
        with self.assertRaises(ValueError):review(rows)
        with self.assertRaises(ValueError):review(waveform()[:-1])

if __name__=='__main__':unittest.main()
