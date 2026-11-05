import unittest
from protect_prototype_parent_periphery import bank_site,rails_for_bank

class PeripheralProtection(unittest.TestCase):
    def boxes(self):return [(50000,100000,384775,434775),(450000,100000,575000,225000),(450000,300000,570000,420000)]
    def test_right_port_gets_a_nearby_bank(self):
        occupied=[(a-3000,b-3000,c+3000,d+3000) for a,b,c,d in self.boxes()]
        x,y=bank_site((575000,180000),4800,occupied)
        self.assertGreaterEqual(x,578000)
        self.assertLess(abs(x+2400-575000)+abs(y+1665-180000),15000)
        self.assertEqual(rails_for_bank((x,y,4800),self.boxes()),(600000,610000))

    def test_rail_connections_do_not_cross_macro(self):
        self.assertEqual(rails_for_bank((400000,150000,4800),self.boxes()),(420000,430000))
        self.assertEqual(rails_for_bank((20000,150000,4800),self.boxes()),(20000,30000))
        with self.assertRaises(ValueError):rails_for_bank((200000,150000,4800),self.boxes())

if __name__=='__main__':unittest.main()
