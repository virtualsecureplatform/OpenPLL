import unittest
from check_selected_einvp_standard_cell_clamp import add_cells


class CellKeeperTests(unittest.TestCase):
    def fixture(self):
        local={p:[n]for p,n in [('Z','z'),('A','a'),('TE','te'),('a_27_47#','enb'),('a_204_47#','n'),('a_276_297#','p'),('VPWR','vp'),('VPB','vp'),('VGND','vn'),('VNB','vn')]}
        cards=['p enb vp vp','z a n vn','vp te enb vp','z a p vp','n te vn vn','vn te enb vn']
        text='.subckt selected_einvp_cut a te vp vn\n'+''.join('Xflat%d %s leaf%d\n'%(i,c,i)for i,c in enumerate(cards))+'.ends selected_einvp_cut\n'
        return text,[dict(cell='cell',local_to_native_nodes=local,flat_MOS_instances=['Xflat%d'%i for i in range(6)])]

    def test_one_complete_cell_added_with_correct_enable_polarity(self):
        text,cells=self.fixture();modified,added,nodes=add_cells(text,cells)
        self.assertEqual(len(added),6);self.assertEqual(len(nodes),3)
        self.assertEqual(added[1]['terminals'],['z','vn','__openpll_keeper_0_n','vn'])
        self.assertEqual(added[4]['terminals'],['__openpll_keeper_0_n','enb','vn','vn'])
        self.assertEqual(added[2]['terminals'],['vp','enb','__openpll_keeper_0_enb','vp'])
        for line in text.splitlines():self.assertIn(line,modified)

    def test_original_geometry_wrappers_reused(self):
        text,cells=self.fixture();_,added,_=add_cells(text,cells)
        self.assertEqual([a['leaf']for a in added],['leaf%d'%i for i in range(6)])

    def test_new_node_collision_rejected(self):
        text,cells=self.fixture()
        with self.assertRaisesRegex(ValueError,'collision'):add_cells('* __openpll_keeper_0_enb\n'+text,cells)


if __name__=='__main__':unittest.main()
