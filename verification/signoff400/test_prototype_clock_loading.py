import unittest
from inventory_prototype_clock_loading import trace

SOURCE = '''.subckt sky130_fd_sc_hs__clkbuf_16 A X
.ends
.subckt sky130_fd_sc_hs__clkinv_1 A Y
.ends
.subckt flop CLK D Q
.ends
.subckt top PLLOUT D
Xroot PLLOUT branch sky130_fd_sc_hs__clkbuf_16
Xinv branch clock sky130_fd_sc_hs__clkinv_1
Xstate clock D Q flop
Xstate2 branch D Q2 flop
.ends
'''


class ClockLoadingControls(unittest.TestCase):
    def test_branches_inverters_and_sequential_frontiers_retained(self):
        r = trace(SOURCE, 'top', 'PLLOUT')
        self.assertEqual(len(r['buffers']), 2)
        self.assertEqual(len(r['frontiers']), 2)
        self.assertTrue(next(x for x in r['buffers'] if x['instance']=='inv')['inverts'])
        self.assertEqual({x['pin'] for x in r['frontiers']}, {'CLK'})
        self.assertFalse(r['clock_timing_qualified'])

    def test_shorted_buffer_rejected(self):
        with self.assertRaises(ValueError):
            trace(SOURCE.replace('Xroot PLLOUT branch', 'Xroot PLLOUT PLLOUT'), 'top', 'PLLOUT')


if __name__ == '__main__':
    unittest.main()
