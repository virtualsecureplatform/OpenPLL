import unittest
from prepare_prototype_context_flat_reference_v2 import original_node
from compare_prototype_physical_primitive_graphs import parsed,expand
from pathlib import Path


class FlatNamespace(unittest.TestCase):
    def test_independent_reparse_recovers_internal_nodes_and_named_alias_ports(self):
        text='''.subckt Top IN OUT ALIAS G
Xflat0 __context_node_0 IN G G sky130_fd_pr__nfet_01v8 l=.15 w=.4
Xflat1 OUT __context_node_0 G G sky130_fd_pr__nfet_01v8 l=.15 w=.4
RwirePort0 ALIAS OUT 0
.ends Top
'''
        _,devices,alias,_,_=expand(parsed(text),'Top',Path('/unused'))
        inverse={'IN':'IN','OUT':'OUT','ALIAS':'ALIAS','G':'G','__context_node_0':'physical/internal'}
        nodes=[tuple(original_node(alias.find(n),inverse,'Top') for n in ns) for _,ns,_ in devices.values()]
        self.assertEqual(nodes,[('physical/internal','IN','G','G'),('OUT','physical/internal','G','G')])
        self.assertEqual(original_node(alias.find('ALIAS'),inverse,'Top'),'OUT')

    def test_unknown_namespace_is_rejected(self):
        with self.assertRaises(ValueError):original_node('Other/__context_node_0',{'__context_node_0':'physical'},'Top')


if __name__=='__main__':unittest.main()
