import unittest
from check_selected_einvp_disabled_clamps import add_clamps,extents


class ClampTests(unittest.TestCase):
    text='.subckt __openpll_literal_leaf_5 d g s b\nXdevice d g s b nfet w=.42 l=.15\n.ends\n.subckt __openpll_literal_leaf_2 d g s b\nXdevice d g s b pfet w=.42 l=.15\n.ends\n.subckt selected_einvp_cut a te vp vn\nXflat1 z a n vn __openpll_literal_leaf_5\nCtest z a 1e-15\n.ends selected_einvp_cut\n'
    cells=[dict(cell='test',local_to_native_nodes={p:[n]for p,n in [('Z','z'),('a_27_47#','enb'),('VGND','vn'),('VNB','vn'),('TE','te'),('VPWR','vp'),('VPB','vp')]})]

    def test_ground_clamp_uses_enable_complement_and_existing_geometry(self):
        text,added=add_clamps(self.text,self.cells,'nfet_to_ground')
        self.assertIn('Xdisabled_clamp0 z enb vn vn __openpll_literal_leaf_5',text)
        self.assertEqual(added[0]['terminals'],['z','enb','vn','vn'])
        self.assertEqual(text.replace('Xdisabled_clamp0 z enb vn vn __openpll_literal_leaf_5\n',''),self.text)

    def test_supply_clamp_uses_TE_and_existing_geometry(self):
        text,_=add_clamps(self.text,self.cells,'pfet_to_supply')
        self.assertIn('Xdisabled_clamp0 z te vp vp __openpll_literal_leaf_2',text)

    def test_missing_geometry_rejected(self):
        with self.assertRaisesRegex(ValueError,'geometry wrapper'):add_clamps(self.text.replace('__openpll_literal_leaf_5','wrong'),self.cells,'nfet_to_ground')

    def test_signed_terminal_ranges_combine_solved_and_recorded_nodes(self):
        result=extents(['TIME','V(XCUT:z)'],[[0.,2.],[5e-9,.1],[1e-8,.2]],['time_s','g','vp'],[[0.,0.,1.8],[1e-8,0.,1.8]],[dict(instance='P',terminals=['z','g','vp','vp'])])
        self.assertEqual(result['P']['DS'],[-1.7,-1.6])
        self.assertEqual(result['P']['GS'],[-1.8,-1.8])
        self.assertEqual(result['P']['BD'],[1.6,1.7])


if __name__=='__main__':unittest.main()
