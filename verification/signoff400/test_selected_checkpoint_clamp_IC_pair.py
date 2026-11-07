import unittest
from run_selected_checkpoint_clamp_IC_pair import clamp_cards


class ClampPairTests(unittest.TestCase):
    text='.subckt __openpll_literal_leaf_5 p0 p1 p2 p3\nXdevice p0 p1 p2 p3 sky130_fd_pr__nfet_01v8 w=.42 l=.15\n.ends __openpll_literal_leaf_5\n'
    def cells(self):return [dict(cell='cell%d'%i,local_to_native_nodes=dict(Z='z%d'%i,**{'a_27_47#':'enb%d'%i},VGND='gnd',VNB='bulk'))for i in range(4)]

    def test_four_ground_clamps_reuse_original_wrapper(self):
        cards,records=clamp_cards(self.text,self.cells())
        self.assertEqual(len(cards.splitlines()),4);self.assertEqual(len(records),4)
        self.assertIn('Xhistory_clamp2 z2 enb2 gnd bulk __openpll_literal_leaf_5',cards)
        self.assertTrue(all(r['geometry_wrapper']=='__openpll_literal_leaf_5'for r in records))

    def test_missing_or_duplicate_cells_rejected(self):
        for cells in [self.cells()[:3],[self.cells()[0]]*4]:
            with self.assertRaisesRegex(ValueError,'four distinct'):clamp_cards(self.text,cells)

    def test_duplicate_outputs_rejected(self):
        cells=self.cells();cells[1]['local_to_native_nodes']['Z']='z0'
        with self.assertRaisesRegex(ValueError,'distinct load-cell outputs'):clamp_cards(self.text,cells)

    def test_wrong_geometry_or_terminated_include_rejected(self):
        for text in [self.text.replace('sky130_fd_pr__nfet_01v8','wrong'),self.text+'.end\n']:
            with self.assertRaises(ValueError):clamp_cards(text,self.cells())


if __name__=='__main__':unittest.main()
