import unittest
from compare_prototype_physical_primitive_graphs import Union
from inventory_selected_dco_load_halo import closure


class PhysicalLoadClosureTest(unittest.TestCase):
    def setUp(self):
        self.bound={k:dict(master=k,primitives=names) for k,names in [('osc',['X0']),('driver',['X1','X2']),('reset',['X3']),('receiver',['X4']),('program',['X5'])]}
        self.pins={'osc':{'O':'out','R':'reset_in'},'driver':{'A':'control','Y':'fine'},'reset':{'Y':'reset_remote'},'receiver':{'A':'out_remote'},'program':{'Y':'control_remote'}}
        self.dirs={'osc':{'O':'OUTPUT','R':'INPUT'},'driver':{'A':'INPUT','Y':'OUTPUT'},'reset':{'Y':'OUTPUT'},'receiver':{'A':'INPUT'},'program':{'Y':'OUTPUT'}}
        self.u=Union()
        for a,b in [('out','out_remote'),('reset_in','reset_remote'),('control','control_remote')]:self.u.join(a,b)

    def test_retains_reset_and_output_load_but_cuts_programming_input_component(self):
        nets,added=closure(self.bound,self.pins,self.dirs,self.u,{'X0','X1','X2'},{'control'})
        self.assertEqual(added,{'reset','receiver'})
        self.assertEqual(len(nets),2)
        self.assertNotIn('program',added)

    def test_rejects_partial_driver_cell(self):
        with self.assertRaisesRegex(ValueError,'physical cell'):
            closure(self.bound,self.pins,self.dirs,self.u,{'X0','X1'},{'control'})


if __name__=='__main__':unittest.main()
