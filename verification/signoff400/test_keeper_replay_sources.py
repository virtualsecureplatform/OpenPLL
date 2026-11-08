import tempfile,unittest
from pathlib import Path
import numpy as np
from write_keeper_replay_sources import write_sources

class ReplaySources(unittest.TestCase):
    def columns(self):return dict(samples=3,ordered_physical_ports=['A','B','PLLOUT'],bindings={'A':dict(role='externally_driven',conditional_formal_port='P0'),'B':dict(role='externally_driven',conditional_formal_port='P1'),'PLLOUT':dict(role='observation_only',conditional_formal_port='P2')})
    def array(self):return np.array([[0.,1.8,0.,0.],[1e-9,1.8,0.12345678901234567,1.],[2e-9,1.8,1.8,0.]])
    def run_writer(self,a=None,c=None):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sources.spice';s=write_sources(self.array() if a is None else a,self.columns() if c is None else c,p);return s,p.read_text()
    def test_only_constant_waveforms_are_reduced(self):
        s,t=self.run_writer();self.assertEqual(s['emitted_PWL_points'],5);self.assertEqual(s['constant_waveforms'],1);self.assertNotIn(' P2 ',t);self.assertIn(format(self.array()[1,2],'.17g'),t)
    def test_output_forcing_rejected(self):
        c=self.columns();c['bindings']['PLLOUT']['role']='externally_driven'
        with self.assertRaises(ValueError):self.run_writer(c=c)
    def test_nonfinite_observation_rejected(self):
        a=self.array();a[1,3]=np.nan
        with self.assertRaises(ValueError):self.run_writer(a=a)
    def test_nonmonotonic_time_rejected(self):
        a=self.array();a[2,0]=a[1,0]
        with self.assertRaises(ValueError):self.run_writer(a=a)
    def test_port_collision_rejected(self):
        c=self.columns();c['bindings']['B']['conditional_formal_port']='P0'
        with self.assertRaises(ValueError):self.run_writer(c=c)

if __name__=='__main__':unittest.main()
