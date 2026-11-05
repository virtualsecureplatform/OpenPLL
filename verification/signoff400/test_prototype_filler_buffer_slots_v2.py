import unittest
from prototype_filler_buffer_slots_v2 import allocate


class CompactSlots(unittest.TestCase):
    def test_compact_inverter_fits_a_three_site_gap(self):
        cells={
            'a':dict(master='sky130_fd_sc_hs__fill_2',bbox=[0,0,960,3330],orient='R0'),
            'b':dict(master='sky130_fd_sc_hs__fill_1',bbox=[960,0,1440,3330],orient='R0')}
        r=dict(name='first',master='sky130_fd_sc_hs__clkinv_1',width=1440,height=3330,anchor=[0,0])
        self.assertEqual(allocate(cells,[r])[0]['bbox'],[0,0,1440,3330])
        with self.assertRaises(ValueError):allocate(cells,[dict(r,width=1920)])

    def test_second_stage_distance_uses_allocated_first_stage(self):
        cells={
            'a':dict(master='sky130_fd_sc_hs__fill_4',bbox=[0,0,1920,3330],orient='R0'),
            'b':dict(master='sky130_fd_sc_hs__fill_4',bbox=[19200,0,21120,3330],orient='R0')}
        first=dict(name='first',master='clkinv',width=1440,height=3330,anchor=[0,0])
        second=dict(name='second',master='clkinv',width=1920,height=3330,anchor=[999999,0],anchor_instance='first')
        result=allocate(cells,[first,second])
        self.assertEqual(result[1]['distance_dbu'],19200)
        self.assertEqual(result[1]['bbox'],[19200,0,21120,3330])


if __name__=='__main__':unittest.main()
