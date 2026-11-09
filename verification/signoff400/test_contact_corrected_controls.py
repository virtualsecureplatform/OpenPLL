import unittest
from check_contact_corrected_controls import bind_observations,assess

class CorrectedControls(unittest.TestCase):
    def observations(self):
        return {f'{bus}{i}.{e}':dict(bus=bus,bit=i,endpoint=e,physical_node=f'n{bus}{i}{e}')
                for bus,width in [('COARSETHERMAL_CODE',47),('DCO_THERM',255)] for i in range(width) for e in ['macro','DCO']}
    def test_all_endpoints_rebound_to_new_native_names(self):
        r=self.observations();nodes={v['physical_node']:f'new{i}' for i,v in enumerate(r.values())}
        roles=bind_observations(r,nodes,{'new0'})
        self.assertEqual(len(roles),604);self.assertEqual(list(roles.values())[:2],['new0','XDUT:new1'])
        nodes.pop(next(iter(nodes)))
        with self.assertRaises(ValueError):bind_observations(r,nodes,set())
    def test_partial_duplicate_and_inverted_fine_logic(self):
        r=self.observations();r.pop(next(iter(r)))
        with self.assertRaises(ValueError):bind_observations(r,{},set())
        small={'a':dict(bus='DCO_THERM',bit=0)}
        self.assertTrue(assess([[0,0],[280e-9,0],[340e-9,0]],small,23,134)[0]['passed'])
        self.assertFalse(assess([[0,0],[280e-9,1],[340e-9,0]],small,23,134)[0]['passed'])
    def test_invalid_capture_rejected(self):
        r={'a':dict(bus='DCO_THERM',bit=0)}
        for rows in [[[0,0],[280e-9,0]],[[0,0],[340e-9,float('nan')]],[[0,0],[340e-9,0],[340e-9,0]]]:
            with self.assertRaises(ValueError):assess(rows,r,23,134)

if __name__=='__main__':unittest.main()
