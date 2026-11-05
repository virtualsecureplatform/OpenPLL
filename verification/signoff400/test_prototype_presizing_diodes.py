import unittest
from presize_prototype_electrical_plan_v2 import mapped_diodes,electrical_driver


class PresizingDiodeMappingTests(unittest.TestCase):
    def full(self):
        return dict(netnames={'signal':{'bits':[100,101]}},cells={'ANTENNA_76':dict(
            type='sky130_fd_sc_hs__diode_2',connections={'DIODE':[101]},port_directions={'DIODE':'input'})})

    def test_named_net_maps_across_projection_bit_renumbering(self):
        logical=dict(netnames={'signal':{'bits':[7,8]}})
        cells=mapped_diodes(self.full(),logical)
        self.assertEqual(electrical_driver('ANTENNA_76/DIODE',{},cells,{8:[('gate','Y')]}),('gate','Y'))

    def test_inconsistent_aliases_rejected(self):
        full=self.full();full['netnames']['alias']={'bits':[101]}
        logical=dict(netnames={'signal':{'bits':[7,8]},'alias':{'bits':[9]}})
        with self.assertRaises(ValueError):mapped_diodes(full,logical)

    def test_unmapped_net_is_not_guessed(self):
        self.assertEqual(mapped_diodes(self.full(),dict(netnames={})),{})

    def test_output_diode_stub_rejected(self):
        full=self.full();full['cells']['ANTENNA_76']['port_directions']['DIODE']='output'
        with self.assertRaises(ValueError):mapped_diodes(full,dict(netnames={}))


if __name__=='__main__':unittest.main()
