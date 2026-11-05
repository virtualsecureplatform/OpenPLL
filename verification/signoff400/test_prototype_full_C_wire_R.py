"""Controls for preserving signed hierarchical compensation when inserting wire resistance."""
from fractions import Fraction as F
import unittest
from build_prototype_full_C_wire_R_v2 import build

SOURCE='''
.subckt Cell A Y Z VPWR VGND
Xmos Y A VGND VGND sky130_fd_pr__nfet_01v8 l=0.15 w=0.42
Cinternal A Z 0.4f
.ends Cell
.subckt Top IN OUT VPWR VGND
XD0 IN wire dpriv VPWR VGND Cell
XR0 wire OUT rpriv VPWR VGND Cell
Cshield wire rpriv -0.2f
.ends Top
'''


def fixture():
    return dict(pin_capacitance_excluded=True,nets=[dict(name='wire',connections=[
        dict(kind='I',node='D0:Y',direction='O'),dict(kind='I',node='R0:A',direction='I')],
        resistors=[dict(nodes=['D0:Y','middle'],ohms='10'),dict(nodes=['middle','R0:A'],ohms='20')],
        capacitors=[dict(nodes=['middle'],farads='999')])])


class FullCapacitanceWireResistance(unittest.TestCase):
    def test_compensation_stays_with_its_positive_capacitance(self):
        # Splitting +0.4 fF onto the receiver and -0.2 fF onto the driver
        # would produce negative energy for driver=1, receiver=private=0.
        for attachment in ('driver','farthest'):
            model,metrics,lift=build(SOURCE,'Top',fixture(),{'D0':'D0','R0':'R0'},attachment)
            capacitors=[line.split() for line in model.splitlines() if line.startswith('Cflat')]
            self.assertEqual(sorted(F(row[3]) for row in capacitors),[F('.2e-15'),F('.4e-15')])
            self.assertEqual(sum(F(row[3]) for row in capacitors),F('.6e-15'))
            self.assertEqual(len([x for x in model.splitlines() if x.startswith('Rwire')]),2)
            devices=[line.split() for line in model.splitlines() if line.startswith('Xflat')]
            self.assertNotEqual(devices[0][1],devices[1][2])
            self.assertEqual(metrics['primitive_instances'],2)
            self.assertTrue(metrics['zero_wire_R_exact_device_topology_and_C_operator_match'])
            self.assertFalse(metrics['wire_capacitance_from_SPEF_added'])
            # Geometric loading placement remains an explicit model choice.
            self.assertEqual(metrics['attachment'],attachment)

    def test_parallel_output_drivers_keep_separate_wire_terminals(self):
        text=SOURCE.replace('XR0 wire OUT', 'XD1 IN wire dpriv2 VPWR VGND Cell\nXR0 wire OUT')
        spef=fixture();net=spef['nets'][0]
        net['connections'].append(dict(kind='I',node='D1:Y',direction='O'))
        net['resistors'].append(dict(nodes=['D0:Y','D1:Y'],ohms='5'))
        model,metrics,_=build(text,'Top',spef,{'D0':'D0','D1':'D1','R0':'R0'})
        self.assertEqual(metrics['primitive_instances'],3)
        self.assertEqual(metrics['wire_resistors'],3)
        self.assertEqual(metrics['rewired_cell_pins'],3)

    def test_shorted_macro_ports_become_finite_wire_endpoints(self):
        text=SOURCE.replace('.subckt Top IN OUT VPWR VGND','.subckt Top IN OUT ALIAS VPWR VGND')
        text=text.replace('.ends Top','Ralias OUT ALIAS 0\nCexternal OUT VGND 0.1f\n.ends Top')
        spef=fixture();spef['nets'].append(dict(name='out',connections=[
            dict(kind='I',node='R0:Y',direction='O'),dict(kind='P',node='OUT',direction='O'),dict(kind='P',node='ALIAS',direction='O')],
            resistors=[dict(nodes=['R0:Y','OUT'],ohms='10'),dict(nodes=['OUT','ALIAS'],ohms='20')],capacitors=[]))
        model,metrics,_=build(text,'Top',spef,{'D0':'D0','R0':'R0'})
        self.assertEqual(metrics['wire_resistors'],4)
        self.assertTrue(metrics['zero_wire_R_exact_device_topology_and_C_operator_match'])
        self.assertEqual(sum(F(line.split()[3]) for line in model.splitlines() if line.startswith('Cflat')),F('.7e-15'))

    def test_disconnected_resistor_graph_is_rejected(self):
        spef=fixture();spef['nets'][0]['resistors'].pop()
        with self.assertRaises(ValueError):build(SOURCE,'Top',spef,{'D0':'D0','R0':'R0'})

    def test_negative_wire_resistance_is_rejected(self):
        spef=fixture();spef['nets'][0]['resistors'][0]['ohms']='-10'
        with self.assertRaises(ValueError):build(SOURCE,'Top',spef,{'D0':'D0','R0':'R0'})


if __name__=='__main__':unittest.main()
