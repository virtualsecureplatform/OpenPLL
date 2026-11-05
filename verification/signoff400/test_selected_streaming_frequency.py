import tempfile,unittest
from pathlib import Path
from compare_selected_streaming_v2 import compare


class StreamingFrequencyTests(unittest.TestCase):
    def test_frequency_uses_late_native_edges(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);ref=p/'ref.csv';candidate=p/'candidate.csv'
            tail=''.join(f'{(200+i)*1e-9:.17g},{i%2}\n' for i in range(61))
            ref.write_text('time_s,v(pllout)\n0,0\n'+tail)
            candidate.write_text('time_s,v(pllout)\n1e-12,0\n'+tail)
            value=compare(ref,candidate,260e-9)['metrics']['v(pllout)']
            self.assertAlmostEqual(value['candidate_frequency_MHz'],500,places=8)
            self.assertEqual(value['frequency_difference_ppm'],0)


if __name__=='__main__':unittest.main()
