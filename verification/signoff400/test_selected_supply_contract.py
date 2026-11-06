import copy,unittest
from check_selected_supply_contract import check,RAILS

class SupplyContract(unittest.TestCase):
    def setUp(self):
        self.p=dict(required_external_nominal_voltages_V=RAILS.copy(),required_external_connections=[['VPWR','VPB'],['VGND','VNB']],internal_rail_shorts_assumed=False,body_bias_mode='zero body bias only')
        self.classes={n:n for n in RAILS}
        self.deck='\n'.join(f'V{i} {n} 0 {v}'for i,(n,v)in enumerate(RAILS.items()))
    def test_explicit_four_pin_contract(self):
        self.assertEqual(check(self.p,self.classes,self.deck)['VPB'],[1.8])
    def test_bad_fixture_rails_rejected(self):
        for deck in (self.deck.replace('VPB 0 1.8','VPB 0 0'),self.deck.replace('V1 VPB 0 1.8',''),self.deck+'\nV4 VPB 0 1.8',self.deck.replace('VPB 0 1.8','VPB VPWR 0'),self.deck.replace('VPB 0 1.8','VPB 0 nan')):
            with self.assertRaises(ValueError):check(self.p,self.classes,deck)
    def test_implicit_shorts_and_wrong_connections_rejected(self):
        for key,value in [('internal_rail_shorts_assumed',True),('required_external_connections',[['VPWR','VNB'],['VPB','VGND']]),('required_external_nominal_voltages_V',{'VPWR':1.8,'VGND':0})]:
            p=copy.deepcopy(self.p);p[key]=value
            with self.assertRaises(ValueError):check(p,self.classes,self.deck)
        with self.assertRaises(ValueError):check(self.p,dict(self.classes,VPB='VPWR'),self.deck)

if __name__=='__main__':unittest.main()
