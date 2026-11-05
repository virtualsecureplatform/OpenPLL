import unittest
from selected_detector_stimulus_ports import declarations

class DetectorStimulusPortsTests(unittest.TestCase):
    def fixture(self):
        ports={'ports':{name:dict(outside_wire_endpoint=name+'in',detector_wire_endpoint=name+'out')
                        for name in ['REF','CLKDIVR','RESET_N','BBPD[0]','BBPD[1]']}}
        event=[dict(pins=dict(D='d'+str(i),CLK='c'+str(i),RESET_B='reset',Q='event'+str(i))) for i in range(2)]
        downstream={str(i):[dict(pins=dict(CLK='fast',RESET_B='fast_reset',Q='sync'+str(i)))] for i in range(2)}
        return ports,dict(selected_cells=event,downstream_sequential_output_cells=downstream)
    def test_outputs_are_not_prescribed_voltage_nodes(self):
        drives,observed=declarations(*self.fixture())
        self.assertEqual(len(drives),6);self.assertEqual(len(observed),6)
        self.assertFalse(set(drives.values())&set(observed.values()))
    def test_shared_drive_and_output_is_rejected(self):
        p,r=self.fixture();r['selected_cells'][0]['pins']['Q']='reset'
        with self.assertRaises(ValueError):declarations(p,r)
    def test_unexpected_reset_domains_are_rejected(self):
        p,r=self.fixture();r['selected_cells'][0]['pins']['RESET_B']='other_reset'
        with self.assertRaises(ValueError):declarations(p,r)

if __name__=='__main__':unittest.main()
