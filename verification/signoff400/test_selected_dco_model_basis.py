import unittest
from audit_selected_dco_model_basis import compare


class DriverAnchorTest(unittest.TestCase):
    def terminal(self,node,kind='I',direction='O'):
        return dict(node=node,kind=kind,direction=direction,ideal_supply_boundary=False,primitive_terminal_positions=[['Xflat1',0]])

    def test_actual_contact_matches_independent_of_token_name(self):
        net=dict(net='ring',context_conductor='C',terminals=[self.terminal('z'),self.terminal('a')])
        rows,n=compare({'networks':[net]},{'capacitor_anchors':{'C':'physical'}},{'Xflat1':['physical']})
        self.assertEqual(n,0);self.assertTrue(rows[0]['same_internal_driver_anchor'])
        self.assertEqual(rows[0]['standalone_policy_first_output'],'a')
        rows,_=compare({'networks':[net]},{'capacitor_anchors':{'C':'other'}},{'Xflat1':['physical']})
        self.assertFalse(rows[0]['same_internal_driver_anchor'])

    def test_external_input_is_not_claimed_equivalent(self):
        net=dict(net='control',context_conductor='C',terminals=[self.terminal('port','P','I')])
        rows,n=compare({'networks':[net]},{'capacitor_anchors':{}},{})
        self.assertEqual(rows,[]);self.assertEqual(n,1)


if __name__=='__main__':unittest.main()
