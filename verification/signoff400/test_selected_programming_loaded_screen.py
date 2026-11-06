import unittest
from run_selected_programming_loaded_screen import slew


class LoadedProgrammingSlewTest(unittest.TestCase):
    def waveform(self):
        return [[t*1e-9,v] for t,v in [(0,0),(4,0),(5,0),(7,1.8),(10,1.8),(12,0),(20,0)]]

    def test_both_directions_use_20_80_crossings(self):
        result=slew(self.waveform(),1)
        self.assertAlmostEqual(result['rise_ps'],1200)
        self.assertAlmostEqual(result['fall_ps'],1200)

    def test_incomplete_and_extra_threshold_edges_rejected(self):
        incomplete=[[t*1e-9,v]for t,v in [(0,0),(5,0),(7,.9),(20,.9)]]
        ringing=[[t*1e-9,v]for t,v in [(0,0),(5,0),(7,1.8),(8,0),(9,1.8),(12,0),(20,0)]]
        for rows in (incomplete,ringing):
            with self.subTest(rows=rows),self.assertRaises(ValueError):slew(rows,1)


if __name__=='__main__':unittest.main()
