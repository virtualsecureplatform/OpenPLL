import unittest
from inventory_selected_detector import logical_port_map,LOGICAL_PORTS,detector_names


class DetectorInventoryTests(unittest.TestCase):
    def test_extracted_SUB_supply_is_bound_from_parent_connectivity(self):
        ports=(LOGICAL_PORTS-{'VGND'})|{'SUB','internal_cap_node'}
        bindings={p:p for p in ports};bindings['SUB']='VGND'
        result=logical_port_map(ports,bindings)
        self.assertEqual(result['VGND'],'SUB')
        self.assertNotIn('internal_cap_node',result.values())
        bindings['internal_cap_node']='VGND'
        with self.assertRaises(ValueError):logical_port_map(ports,bindings)

    def test_selected_physical_master_must_be_detector(self):
        def item(name,master):return dict(instance=name,physical_hierarchy_identity=[['top','scale',[master]]])
        values=[item('Xflat1','IntegerPLL_BBPD'),item('Xflat2','IntegerPLL_DCO')]
        self.assertEqual(detector_names(values),{'Xflat1'})
        with self.assertRaises(ValueError):detector_names(values[1:])


if __name__=='__main__':unittest.main()
