import unittest
from extract_prototype_parent_spef import check_network

class ParentWireConnectivity(unittest.TestCase):
    def test_resistive_path_connects_terminals(self):
        net=dict(name='clock',connections=[dict(node=n) for n in ('driver','sink')],resistors=[dict(nodes=['driver','middle']),dict(nodes=['middle','sink'])],capacitors=[])
        self.assertEqual(check_network(net)['terminals'],2)
        net['resistors'].pop()
        net['capacitors']=[dict(nodes=['middle','sink'])]
        with self.assertRaises(ValueError):check_network(net)

    def test_empty_wire_is_not_connected(self):
        with self.assertRaises(ValueError):check_network(dict(name='empty',connections=[],resistors=[],capacitors=[]))

if __name__=='__main__':unittest.main()
