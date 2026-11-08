import unittest
import numpy as np
from aggregate_keeper_boundary_waveforms import aggregate
from reduce_keeper_capacitor_boundaries import transform
import test_reduce_keeper_capacitor_boundaries as fixture_module

class Aggregation(unittest.TestCase):
    def fixture(self):
        text,b=fixture_module.CapacitorReduction().fixture();_,reduced,certificate=transform(text,b)
        columns=dict(samples=3,ordered_physical_ports=['A','B','VPWR','PLLOUT'],bindings={k:dict(role='observation_only' if k=='PLLOUT' else 'externally_driven',conditional_formal_port=v) for k,v in b['all_physical_nodes'].items()})
        array=np.array([[0.,0.,0.,1.8,.4],[1.,1.,0.,1.8,.8],[2.,0.,1.,1.8,1.2]])
        return array,columns,reduced,certificate
    def test_exact_weighted_samples_and_unforced_output(self):
        array,c,b,cert=self.fixture();result,columns,audit=aggregate(array,c,b,cert)
        np.testing.assert_array_equal(result[:,0],array[:,0]);np.testing.assert_array_equal(result[:,-1],array[:,-1])
        j=columns['ordered_physical_ports'].index('CAP_AGGREGATE[0]')+1
        np.testing.assert_array_equal(result[:,j],[0.,.25,.75])
        self.assertEqual(audit['groups'][0]['maximum_sample_absolute_voltage_error_exact'],'0')
        self.assertFalse(audit['native_simulation_allowed'])
    def test_invalid_coefficients_and_observation_forcing_rejected(self):
        a,c,b,cert=self.fixture();cert['groups'][0]['boundary_weights_exact']['A']='1/3'
        with self.assertRaisesRegex(ValueError,'coefficients'):aggregate(a,c,b,cert)
        a,c,b,cert=self.fixture();g=cert['groups'][0]
        for field in ['boundary_weights_exact','original_boundary_C_F_exact']:g[field]['PLLOUT']=g[field].pop('A')
        with self.assertRaisesRegex(ValueError,'driven boundaries'):aggregate(a,c,b,cert)
    def test_rounded_samples_have_nonzero_exact_error(self):
        a,c,b,cert=self.fixture();a[1,1]=.1
        _,_,audit=aggregate(a,c,b,cert)
        # Binary division by four is exact; force a nonbinary weight instead.
        g=cert['groups'][0];g['boundary_weights_exact']={'A':'1/3','B':'2/3'};g['original_boundary_C_F_exact']={'A':'1/750000000000000','B':'1/375000000000000'}
        _,_,audit=aggregate(a,c,b,cert)
        self.assertNotEqual(audit['groups'][0]['maximum_sample_absolute_voltage_error_exact'],'0')
if __name__=='__main__':unittest.main()
