import unittest
from bind_selected_detector_ports import bind,SIGNALS


class DetectorPortsTests(unittest.TestCase):
    def test_old_names_are_mapped_through_wire_contraction(self):
        inv=dict(detector_signal_nodes=[],logical_parent_bindings={},wire_edges_crossing_detector_node_set=[])
        nodes={};wire=dict(generated_node_to_source_conductor={})
        for i,role in enumerate(SIGNALS):
            old='logical'+str(i);actual='physical'+str(i);outside='outside'+str(i)
            inv['logical_parent_bindings'][role]=old;nodes[old]='conductor'+str(i)
            inv['detector_signal_nodes'].append(actual)
            inv['wire_edges_crossing_detector_node_set'].append(dict(card='R'+str(i),nodes=[actual,outside],value='1'))
            wire['generated_node_to_source_conductor'].update({actual:nodes[old],outside:nodes[old]})
        result=bind(inv,nodes,wire)
        self.assertEqual(result['BBPD[0]']['detector_wire_endpoint'],'physical3')
        inv['wire_edges_crossing_detector_node_set'].append(inv['wire_edges_crossing_detector_node_set'][0])
        with self.assertRaises(ValueError):bind(inv,nodes,wire)


if __name__=='__main__':unittest.main()
