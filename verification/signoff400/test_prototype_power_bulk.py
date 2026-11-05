import unittest
from collections import Counter
from check_prototype_power_bulk_topology_v2 import check

PARAMS=tuple(sorted(dict(l='0.15',w='1',ad='0.1',**{'as':'0.1'},pd='1',ps='1').items()))


class PowerBulkControls(unittest.TestCase):
    def test_declared_nmos_ground_and_pmos_positive_bulk(self):
        cards=Counter({('sky130_fd_pr__nfet_01v8',('D','G','VGND','VNB'),PARAMS):2,
                       ('sky130_fd_pr__pfet_01v8',('D','G','VPWR','VPB'),PARAMS):2})
        self.assertTrue(check(cards)['power_bulk_topology_and_parameter_signs_pass'])
        shorted=Counter({('sky130_fd_pr__pfet_01v8',('D','G','VPWR','VGND'),PARAMS):1})
        self.assertFalse(check(shorted)['power_bulk_topology_and_parameter_signs_pass'])

    def test_floating_bulk_and_negative_junction_parameters_rejected(self):
        for bulk,params in [('floating',PARAMS),('VGND',tuple((k,'-1' if k=='ad' else v) for k,v in PARAMS))]:
            cards=Counter({('sky130_fd_pr__nfet_01v8',('D','G','VGND',bulk),params):1})
            self.assertFalse(check(cards)['power_bulk_topology_and_parameter_signs_pass'])

    def test_reviewed_poly_model_is_two_terminal_and_positive_dimension(self):
        for nodes,params,expected in [(('a','b'),(('l','0.045'),('w','0.51')),True),
                                      (('a','b','bulk'),(('l','0.045'),('w','0.51')),False),
                                      (('a','b'),(('l','-1'),('w','0.51')),False)]:
            with self.subTest(nodes=nodes,params=params):
                self.assertEqual(check(Counter({('sky130_fd_pr__res_generic_po',nodes,params):1}))['power_bulk_topology_and_parameter_signs_pass'],expected)


if __name__=='__main__':unittest.main()
