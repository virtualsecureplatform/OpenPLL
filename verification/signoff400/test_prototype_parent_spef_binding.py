from fractions import Fraction
import unittest
from bind_prototype_parent_spef import join_parent

class ParentPlacementJoin(unittest.TestCase):
    def fixture(self):
        rows=[('leaf','sky130_fd_sc_hs__inv_2',1000,2000),
              ('digital','IntegerPLL_ProgrammedCore',50000,100000),
              ('oscillator','IntegerPLL_DCO_test',450000,100000),
              ('detector','IntegerPLL_BBPD',450000,300000)]
        placements='UNITS\t1000\n'+''.join(f'INST\t{name}\t{master}\tR0\t{x}\t{y}\t1000\t1000\n' for name,master,x,y in rows)
        ext=''.join(f'use {master} extracted_{name} 1 0 {x//5} 0 1 {y//5}\n' for name,master,x,y in rows)
        return placements,ext

    def test_exact_grid_join_covers_macro_and_standard_instances(self):
        placements,ext=self.fixture();mapping,scale=join_parent(placements,ext,Fraction(1,200))
        self.assertEqual(len(mapping),4);self.assertEqual(scale,5)
        self.assertEqual({r['routed_instance'] for r in mapping},{'leaf','digital','oscillator','detector'})

    def test_one_dbu_error_or_duplicate_extracted_macro_rejected(self):
        placements,ext=self.fixture()
        with self.assertRaises(ValueError):join_parent(placements.replace('\t50000\t','\t50001\t'),ext,Fraction(1,200))
        duplicate='use IntegerPLL_ProgrammedCore other 1 0 10000 0 1 20000\n'
        with self.assertRaises(ValueError):join_parent(placements,ext+duplicate,Fraction(1,200))

if __name__=='__main__':unittest.main()
