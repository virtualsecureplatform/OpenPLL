import unittest
from protect_prototype_compact_parent import bank_site,diode_count,X0,Y0,SX,SY

class CompactProtection(unittest.TestCase):
    def test_diodes_cover_measured_ratio_with_explicit_allowance(self):
        record=dict(stage='m4',ratio=4094,diffusion_area_um2=.739)
        count=diode_count(record,.6417)
        self.assertGreaterEqual(400+2200+400*(.739+count*.6417),4094*1.25)
        self.assertEqual(diode_count(dict(stage='m3',ratio=500,diffusion_area_um2=0),.6417),4)
        with self.assertRaises(ValueError):diode_count(dict(record,stage='v1'),.6417)

    def test_corridor_placement_and_occupied_bank_clearance(self):
        width=4800
        x,y=bank_site((450000,150000),width,[])
        self.assertEqual((x-X0)%SX,0)
        self.assertEqual((y-Y0)%(2*SY),0)
        self.assertGreaterEqual(x,388000);self.assertLessEqual(x+width,447000)
        occupied=[(x-1920,y-245,x+width+1920,y+SY+245)]
        a,b=bank_site((450000,150000),width,occupied)
        self.assertTrue(a+width<=occupied[0][0] or a>=occupied[0][2] or b+SY<=occupied[0][1] or b>=occupied[0][3])
        with self.assertRaises(ValueError):bank_site((450000,150000),width,[(0,0,650000,500000)])

if __name__=='__main__':unittest.main()
