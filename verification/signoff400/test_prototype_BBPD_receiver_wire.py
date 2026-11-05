import copy
import unittest
from bind_prototype_BBPD_receiver_wire import bind


def fixture():
    module=dict(cells={'buf':dict(connections={'A':[1],'X':[2]},port_directions={'A':'input','X':'output'})})
    def network(name,connections,edges):
        return dict(name=name,connections=connections,resistors=[dict(id='1',nodes=list(edges),ohms='1')],capacitors=[dict(id='1',nodes=[edges[0]],farads='1/1000000000000000')],declared_capacitance_F='1/1000000000000000')
    spef=dict(pin_capacitance_excluded=True,nets=[
        network('input',[dict(kind='P',node='IN',direction='I'),dict(kind='I',node='buf:A',direction='I')],('IN','buf:A')),
        network('output',[dict(kind='I',node='buf:X',direction='O'),dict(kind='I',node='external:A',direction='I')],('buf:X','external:A'))])
    return module,spef


class ReceiverWireBindingIntegrity(unittest.TestCase):
    def test_terminal_binding_retains_outside_loads_and_wire_elements(self):
        m,s=fixture();r=bind(m,['buf'],s)
        self.assertEqual(r['selected_terminals'],2)
        self.assertEqual(r['selected_networks'],2)
        self.assertEqual(r['networks'][1]['outside_terminals'][0]['node'],'external:A')
        self.assertEqual(len(r['networks'][1]['resistors']),1)
        self.assertFalse(r['outside_receiver_pin_capacitance_bounded'])

    def test_missing_disconnected_or_shorted_terminal_networks_rejected(self):
        m,s=fixture()
        missing=copy.deepcopy(s);missing['nets'].pop()
        disconnected=copy.deepcopy(s);disconnected['nets'][0]['resistors']=[]
        shorted=copy.deepcopy(s);shorted['nets'][0]['connections'].append(dict(kind='I',node='buf:X',direction='O'))
        direction=copy.deepcopy(s);direction['nets'][0]['connections'][1]['direction']='O'
        for bad in (missing,disconnected,shorted,direction):
            with self.assertRaises(ValueError):bind(m,['buf'],bad)


if __name__=='__main__':unittest.main()
