import unittest
from review_prototype_exercised_clocks import observe


def row(kind,time,level=1,fine=8,frequency=400000000000):
    return dict(event=kind,time_ps=str(time),level=str(level),coarse='20',fine=str(fine),frequency_millihz=str(frequency))


class ExercisedClocks(unittest.TestCase):
    def test_reset_gaps_and_startup_hold_do_not_create_short_cycles(self):
        rows=[row('RESET',0),row('TUNE',1000),row('START',1500),row('EDGE',2750,0),
              row('EDGE',4000),row('EDGE',5250,0),row('EDGE',6500),row('RESET',7000),
              row('TUNE',20000),row('EDGE',21250,0),row('EDGE',22500)]
        a=observe(rows,{(20,8):400000000000})
        self.assertEqual(a['minimum_rising_period_ps'],2500)
        self.assertEqual((a['minimum_low_ps'],a['minimum_high_ps']),(1250,1250))

    def test_table_mismatch_and_non_alternating_edges_rejected(self):
        for rows in ([row('TUNE',0,frequency=410000000000)],
                     [row('TUNE',0),row('EDGE',1000,0),row('EDGE',2000,0)]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):observe(rows,{(20,8):400000000000})


if __name__=='__main__':unittest.main()
