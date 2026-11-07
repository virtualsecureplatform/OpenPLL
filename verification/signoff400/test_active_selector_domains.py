import unittest
import pya
from check_keeper_active_selectors import domains

class SelectorDomains(unittest.TestCase):
    def region(self,a,b):return pya.Region(pya.Box(a,0,b,10))
    def base(self):return {n:pya.Region()for n in ['poly','diff','tap','diode','polyres','licon','rpm','urpm']}
    def test_outside_domain_difference_remains_full_mask_difference(self):
        before=self.region(0,10);after=self.region(1,9);active=self.region(2,8)
        self.assertFalse((before^after).is_empty());self.assertTrue(((before^after)&active).is_empty())
    def test_changed_selector_inside_gate_is_detected(self):
        regions=self.base();regions['poly']=self.region(2,8);regions['diff']=self.region(3,7)
        source=self.region(1,9);changed=source-self.region(4,5)
        self.assertFalse(((source^changed)&domains(regions)['lvtn']).is_empty())
    def test_implant_domain_includes_body_taps(self):
        regions=self.base();regions['tap']=self.region(3,7)
        self.assertFalse((domains(regions)['nsdm']&self.region(4,5)).is_empty())
    def test_NPC_domain_includes_marked_high_resistance_poly(self):
        regions=self.base();regions['poly']=self.region(1,9);regions['polyres']=self.region(2,8);regions['rpm']=self.region(3,7)
        self.assertFalse((domains(regions)['npc']&self.region(4,5)).is_empty())

if __name__=='__main__':unittest.main()
