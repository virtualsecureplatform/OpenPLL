import unittest
from prepare_prototype_DCO_scope_controls import contract_wire_resistors

class ScopeControlTests(unittest.TestCase):
    def test_contracts_wire_without_moving_local_cell_capacitors(self):
        text='''.subckt cell A Z
Xmos A A Z Z sky130_fd_pr__nfet_01v8 w=1 l=1
Cinternal A Z -0.1f
Cparallel A Z 2f
.ends cell
.subckt TOP INPUT OUTPUT
Xone near end cell
R1 INPUT near 2
R2 end OUTPUT 3
Cwire near end 4f
.ends TOP
'''
        result,receipt=contract_wire_resistors(text,'TOP')
        self.assertIn('Cinternal A Z -0.1f',result)
        self.assertIn('Xone INPUT OUTPUT cell',result)
        self.assertIn('Cwire INPUT OUTPUT 4f',result)
        self.assertNotIn('R1 ',result)
        self.assertTrue(receipt['exact_zero_R_device_and_signed_C_identity_verified'])

    def test_primary_short_and_nonpositive_resistance_rejected(self):
        for card,message in [('R1 INPUT OUTPUT 2','shorts primary'),('R1 INPUT n 0','positive explicit')]:
            with self.assertRaisesRegex(ValueError,message):
                contract_wire_resistors('.subckt TOP INPUT OUTPUT\n'+card+'\n.ends TOP\n','TOP')

if __name__=='__main__':unittest.main()
