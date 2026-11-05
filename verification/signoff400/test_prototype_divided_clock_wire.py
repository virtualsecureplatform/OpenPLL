import copy
import unittest
from prepare_prototype_divided_clock_wire import build


def fixture():
    module=dict(ports={'CLKDIV_RETIMED':dict(bits=[13])},cells={
        'source':dict(type='sky130_fd_sc_hs__dfrtp_1',connections={'Q':[13]},port_directions={'Q':'output'}),
        'load0':dict(type='sky130_fd_sc_hs__clkbuf_16',connections={'A':[13]},port_directions={'A':'input'}),
        'load1':dict(type='sky130_fd_sc_hs__clkbuf_16',connections={'A':[13]},port_directions={'A':'input'})})
    net=dict(name='CLKDIV',declared_capacitance_F='3/1000000000000000',connections=[
        dict(kind='I',node='source:Q',direction='O'),dict(kind='I',node='load0:A',direction='I'),
        dict(kind='I',node='load1:A',direction='I'),dict(kind='P',node='CLKDIV_RETIMED',direction='O')],
        resistors=[dict(nodes=['source:Q','load0:A'],ohms='1'),dict(nodes=['load0:A','load1:A'],ohms='2'),dict(nodes=['load1:A','CLKDIV_RETIMED'],ohms='3')],
        capacitors=[dict(nodes=['CLKDIV_RETIMED'],farads='1/1000000000000000'),dict(nodes=['load0:A','external:1'],farads='2/1000000000000000')])
    return module,dict(nets=[net])


class DividedClockWire(unittest.TestCase):
    def test_actual_driver_loads_port_and_external_coupling_preserved(self):
        text,mapping=build(*fixture())
        self.assertEqual(mapping['wire_resistors'],3)
        self.assertEqual(mapping['wire_capacitors'],2)
        self.assertEqual(mapping['terminal_binding']['source:Q'],'SOURCEQ')
        self.assertEqual(mapping['terminal_binding']['CLKDIV_RETIMED'],'DIV')
        self.assertIn('CLKLOAD0 AGGR0',text)
        self.assertEqual(mapping['off_network_aggressors'],[dict(port='AGGR0',spef_node='external:1')])

    def test_missing_or_disconnected_actual_terminal_rejected(self):
        m,s=fixture();s['nets'][0]['connections'].pop(2)
        with self.assertRaises(ValueError):build(m,s)
        m,s=fixture();s['nets'][0]['resistors'].pop()
        with self.assertRaises(ValueError):build(m,s)

    def test_unreviewed_source_and_negative_wire_resistance_rejected(self):
        m,s=fixture();m['cells']['source']['type']='sky130_fd_sc_hs__dfrtp_4'
        with self.assertRaises(ValueError):build(m,s)
        m,s=fixture();s['nets'][0]['resistors'][0]['ohms']='-1'
        with self.assertRaises(ValueError):build(m,s)


if __name__=='__main__':unittest.main()
