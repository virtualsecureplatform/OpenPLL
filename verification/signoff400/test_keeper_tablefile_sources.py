import tempfile,unittest
from pathlib import Path
import numpy as np
from write_keeper_tablefile_sources import write_sources
class TableSources(unittest.TestCase):
    def fixture(self):
        a=np.array([[0.,.1,1.8,0.],[.13e-9,.4,1.8,1.],[4e-9,-.2,1.8,0.]])
        c=dict(samples=3,ordered_physical_ports=['A','RAIL','PLLOUT'],bindings={n:dict(role='observation_only' if n=='PLLOUT' else 'externally_driven',conditional_formal_port='p'+str(i)) for i,n in enumerate(['A','RAIL','PLLOUT'])})
        return a,c
    def test_all_varying_samples_roundtrip_and_output_not_driven(self):
        a,c=self.fixture()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sources';r=write_sources(a,c,p)
            np.testing.assert_array_equal(np.loadtxt(p.parent/'tables/0.dat'),a[:,[0,1]])
            np.testing.assert_array_equal(np.loadtxt(p.parent/'tables/1.dat'),a[[0,-1]][:,[0,2]])
            text=p.read_text();self.assertEqual(text.count('TABLEFILE('),2);self.assertNotIn('p2',text);self.assertFalse(r['downsampling_requested']);self.assertFalse(r['PLLOUT_forced'])
    def test_nonfinite_or_output_role_change_rejected(self):
        a,c=self.fixture();a[1,1]=float('nan')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'nonfinite'):write_sources(a,c,Path(d)/'sources')
        a,c=self.fixture();c['bindings']['PLLOUT']['role']='externally_driven'
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'unforced'):write_sources(a,c,Path(d)/'sources')
if __name__=='__main__':unittest.main()
