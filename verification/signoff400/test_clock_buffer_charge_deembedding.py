import unittest
import numpy as np
from clock_buffer_charge_deembedding import deembed


class ChargeDeembedding(unittest.TestCase):
    def waveforms(self,total_f):
        t=np.linspace(0,34e-9,17001)
        v=np.interp(t,np.array([0,9.8,10.2,21.8,22.2,34])*1e-9,[0,0,1.8,1.8,0,0])
        current=-total_f*np.gradient(v,t)
        return t,v,current

    def capacitor(self,other):
        return dict(name='C1',nodes=['A',other],literal='2f',value_F_exact='1/500000000000000')

    def test_opposite_moving_neighbor_contributes_twice_its_C(self):
        t,v,i=self.waveforms(7e-15)
        result=deembed(t,v,i,v,1.8-v,[self.capacitor('a_114_74#')],400)
        for row in result.values():
            self.assertAlmostEqual(row['explicit_effective_capacitance_F']/1e-15,4.,places=8)
            self.assertAlmostEqual(row['intrinsic_effective_capacitance_F']/1e-15,3.,places=8)

    def test_fixed_rail_offset_does_not_change_charge_increment(self):
        t,v,i=self.waveforms(5e-15)
        result=deembed(t,v,i,v,1.8-v,[self.capacitor('VPWR')],400)
        for row in result.values():
            self.assertAlmostEqual(row['intrinsic_effective_capacitance_F']/1e-15,3.,places=8)

    def test_unobserved_node_duplicate_or_changed_capacitor_rejected(self):
        t,v,i=self.waveforms(5e-15)
        good=self.capacitor('VPWR')
        for caps in ([self.capacitor('missing')],[good,good],[dict(good,literal='3f')]):
            with self.assertRaises(ValueError):deembed(t,v,i,v,1.8-v,caps,400)


if __name__=='__main__':
    unittest.main()
