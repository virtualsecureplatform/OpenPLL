from pathlib import Path
import tempfile
import unittest
from write_prototype_observed_reset_load_liberty import preload_check


class PreloadStatesTest(unittest.TestCase):
    def test_stored_data_and_asynchronous_reset_are_distinct(self):
        points=[dict(fixture=dict(master='sky130_fd_sc_hs__dfrtp_1__final_C',data=1)),
                dict(fixture=dict(master='sky130_fd_sc_hs__dfstp_1__final_C',data=0))]
        with tempfile.TemporaryDirectory() as directory:
            point=Path(directory);wave=point/'batch.prn'
            text='Index TIME V0 I0 Q0 V1 I1 Q1\n'
            for i,t in enumerate((6.8e-9,6.9e-9,13e-9,13.1e-9)):
                q0,q1=(1.8,0) if i<2 else (0,1.8)
                text+=f'{i} {t} 0 0 {q0} 0 0 {q1}\n'
            wave.write_text(text)
            self.assertEqual(preload_check(point,points),[2,2])
            wave.write_text(text.replace('0 0 1.8 0 0 0','0 0 0 0 0 0',1))
            with self.assertRaises(ValueError):preload_check(point,points)


if __name__=='__main__':unittest.main()
