import copy
import unittest
from inventory_mapped_CDC import inventory
from compare_mapped_routed_CDC import normalized,clock_roots,identifier
from test_mapped_CDC_inventory import fixture


class RoutedClockControls(unittest.TestCase):
    def clock_tree(self,inversions):
        m=copy.deepcopy(fixture());last=5
        for i in range(inversions+1):
            bit=20+i;kind='clkbuf' if i==0 else 'clkinv'
            m['cells']['clock_'+str(i)]=dict(type='sky130_fd_sc_hs__'+kind+'_4',
                port_directions=dict(A='input',Y='output'),connections=dict(A=[last],Y=[bit]))
            last=bit
        for n in ('meta','sync'):m['cells'][n]['connections']['CLK']=[last]
        return m

    def test_buffers_and_even_inversions_preserve_roots_but_odd_inversion_is_retained(self):
        original=fixture();before,_=normalized(original,inventory(original))
        for inversions in (0,2):
            tree=self.clock_tree(inversions);after,_=normalized(tree,inventory(tree));self.assertEqual(before,after)
        tree=self.clock_tree(1);after,_=normalized(tree,inventory(tree));self.assertNotEqual(before['meta']['clock_root'],after['meta']['clock_root'])

    def test_unreviewed_gates_and_clock_cycles_rejected_and_escaping_scoped(self):
        m=self.clock_tree(0);m['cells']['clock_0']['type']='sky130_fd_sc_hs__and2_1'
        with self.assertRaises(ValueError):clock_roots(m)(20)
        m=self.clock_tree(0);m['cells']['clock_0']['connections']['A']=[20]
        with self.assertRaises(ValueError):clock_roots(m)(20)
        self.assertEqual(identifier('\\\\$auto$ff.cc:337:slice$1'),'$auto$ff.cc:337:slice$1')
        self.assertEqual(identifier('\\user_name'),'\\user_name')


if __name__=='__main__':unittest.main()
