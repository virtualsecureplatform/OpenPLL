import unittest
from prototype_filler_buffer_slots import allocate,partition


class FillerSlots(unittest.TestCase):
    def test_buffer_spans_adjacent_fillers_without_moving_logic(self):
        cells={f'f{i}':dict(master='sky130_fd_sc_hs__fill_8',bbox=[i*3840,0,(i+1)*3840,3330],orient='MX') for i in range(2)}
        cells['logic']=dict(master='nand2_1',bbox=[7680,0,9000,3330],orient='MX')
        request=dict(name='buffer',master='sky130_fd_sc_hs__clkbuf_8',width=5280,height=3330,anchor=[960,0])
        result=allocate(cells,[request])[0]
        self.assertEqual(result['donors'],['f0','f1']);self.assertEqual(result['bbox'],[960,0,6240,3330])
        self.assertNotIn('logic',result['donors']);self.assertEqual(result['orient'],'MX')

    def test_sequential_slots_do_not_overlap(self):
        cells={'f':dict(master='sky130_fd_sc_hs__fill_8',bbox=[0,0,3840,3330],orient='R0')}
        requests=[dict(name=f'b{i}',master='sky130_fd_sc_hs__clkbuf_2',width=1920,height=3330,anchor=[0,0]) for i in range(2)]
        a,b=allocate(cells,requests)
        self.assertLessEqual(a['bbox'][2],b['bbox'][0])
        with self.assertRaises(ValueError):allocate(cells,requests+[dict(requests[0],name='b2')])

    def test_distance_bound_and_exact_odd_site_leftovers(self):
        self.assertEqual(partition(0,1440,480),[(0,'sky130_fd_sc_hs__fill_2'),(960,'sky130_fd_sc_hs__fill_1')])
        cells={'f':dict(master='sky130_fd_sc_hs__fill_8',bbox=[0,0,3840,3330],orient='R0')}
        r=dict(name='b',master='sky130_fd_sc_hs__clkbuf_2',width=1920,height=3330,anchor=[30000,0])
        with self.assertRaises(ValueError):allocate(cells,[r])


if __name__=='__main__':unittest.main()
