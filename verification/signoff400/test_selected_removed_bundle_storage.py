import copy,unittest
from audit_selected_removed_bundle_storage import analyze

class RemovedBundleStorage(unittest.TestCase):
    def fixture(self):
        module=dict(cells={'ff':dict(type='sky130_fd_sc_hs__dfrtp_1',connections={'Q':[11],'D':[3],'CLK':[2],'RESET_B':[1]},port_directions={'Q':'output','D':'input','CLK':'input','RESET_B':'input'})},ports={'out':dict(direction='output',bits=[11])},netnames={'bundle':dict(bits=[11,12,'x'])})
        bundles=[dict(id='bundle',logical_width=3,implemented_destination_registers=[dict(logical_bit=0,mapped_cell='ff')])]
        return module,bundles
    def test_unused_integer_and_unknown_aliases_are_not_invented_constants(self):
        m,b=self.fixture();r=analyze(m,b)[0]
        self.assertEqual(r['implemented_bits'],[0]);self.assertEqual(len(r['removed_bits']),2)
        self.assertTrue(r['removed_storage_unobservable_in_mapped_hardware'])
    def test_reintroduced_cell_or_module_endpoint_is_rejected(self):
        for direction in ('input','output'):
            m,b=self.fixture();m['cells']['extra']=dict(type='probe',connections={'A':[12]},port_directions={'A':direction})
            with self.subTest(direction=direction),self.assertRaises(ValueError):analyze(m,b)
        m,b=self.fixture();m['ports']['leak']=dict(direction='output',bits=[12])
        with self.assertRaises(ValueError):analyze(m,b)
    def test_unknown_active_consumer_and_unreviewed_literal_rejected(self):
        m,b=self.fixture();m['cells']['ff']['connections']['D']=['x']
        with self.assertRaises(ValueError):analyze(m,b)
        m,b=self.fixture();m['ports']['out']['bits']=['x']
        with self.assertRaises(ValueError):analyze(m,b)
        m,b=self.fixture();m['netnames']['bundle']['bits'][2]='1'
        with self.assertRaises(ValueError):analyze(m,b)
    def test_wrong_capture_driver_or_duplicate_mapping_rejected(self):
        m,b=self.fixture();m['cells']['ff']['connections']['Q']=[99]
        with self.assertRaises(ValueError):analyze(m,b)
        m,b=self.fixture();b[0]['implemented_destination_registers']*=2
        with self.assertRaises(ValueError):analyze(m,b)

if __name__=='__main__':unittest.main()
