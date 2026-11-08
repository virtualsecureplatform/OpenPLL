import unittest,tempfile
from pathlib import Path
import numpy as np
from write_keeper_shared_tablefile_sources import write_sources
class SharedSources(unittest.TestCase):
    def fixture(self):
        return np.array([[0.,.1,0.],[.13e-9,.4,1.],[4e-9,-.2,0.]]),dict(samples=3,ordered_physical_ports=['A','PLLOUT'],bindings={'A':dict(role='externally_driven',conditional_formal_port='p0'),'PLLOUT':dict(role='observation_only',conditional_formal_port='p1')})
    def test_shared_knots_and_literal_samples_preserved(self):
        a,c=self.fixture()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sources';r=write_sources(a,c,p);text=p.read_text()
            np.testing.assert_array_equal(np.loadtxt(p.parent/'tables/0.dat'),a[:,[0,1]])
            carrier=text.split('PWL(\n',1)[1].split('+ )',1)[0];times=[float(line.split()[1]) for line in carrier.splitlines()]
            self.assertEqual(times,list(a[:,0]));self.assertEqual(text.count('FASTTABLEFILE('),1);self.assertNotIn(' p1 ',text);self.assertTrue(r['all_original_time_knots_requested']);self.assertFalse(r['PLLOUT_forced'])
    def test_auxiliary_node_collision_rejected(self):
        a,c=self.fixture();c['bindings']['A']['conditional_formal_port']='openpll_replay_time_knots'
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'collides'):write_sources(a,c,Path(d)/'sources')
if __name__=='__main__':unittest.main()
