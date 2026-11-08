import unittest
from pathlib import Path
from run_keeper_flat_corner_DC import corner_deck

class CornerDC(unittest.TestCase):
    def text(self):return '.lib "pdk.lib" tt\n.include "backend.spice"\nVRESET RESET_N 0 0\n.options device temp=27\n.dc VRESET 0 0 1\n.print dc format=csv file=/reference/dc.csv v(PLLOUT)\n.end\n'
    def test_only_corner_and_output_path_change(self):
        for corner in ['ff','ss','sf','fs']:
            self.assertEqual(corner_deck(self.text(),Path('/reference'),Path('/case'),corner),self.text().replace('.lib "pdk.lib" tt','.lib "pdk.lib" '+corner).replace('/reference/dc.csv','/case/dc.csv'))
    def test_unexpected_domain_rejected(self):
        for text,corner in [(self.text(),'tt'),(self.text().replace('temp=27','temp=85'),'ff'),(self.text().replace('.dc VRESET 0 0 1','.tran 10p 260n'),'ff')]:
            with self.assertRaises(ValueError):corner_deck(text,Path('/reference'),Path('/case'),corner)

if __name__=='__main__':unittest.main()
