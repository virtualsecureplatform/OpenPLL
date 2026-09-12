#!/usr/bin/env python3
import unittest
import numpy as np
from reduce_spice_resistors import reduce_network


def port_admittance(text, frequency):
    elements=[];nodes=set()
    for line in text.splitlines():
        t=line.split()
        if t and t[0][0].lower() in ('r','c'):
            elements.append(t);nodes.update(t[1:3])
    nodes=['a','b']+sorted(nodes-{'a','b','0'})
    y=np.zeros((len(nodes),len(nodes)),complex)
    for name,a,b,value in elements:
        g=1/float(value) if name[0].lower()=='r' else 2j*np.pi*frequency*float(value)
        for node in [a,b]:
            if node!='0':y[nodes.index(node),nodes.index(node)]+=g
        if a!='0' and b!='0':
            i,j=nodes.index(a),nodes.index(b);y[i,j]-=g;y[j,i]-=g
    if len(nodes)==2:return y
    return y[:2,:2]-y[:2,2:]@np.linalg.solve(y[2:,2:],y[2:,:2])


class ResistorReductionTests(unittest.TestCase):
    def test_dynamic_terminal_admittance_is_preserved(self):
        text='''.subckt cell a b 0
R1 a x 2
R2 x y 3
R3 y 0 7
R4 y b 5
R5 x b 11
R6 x leaf 10
C1 y 0 1e-12
.ends
'''
        reduced,stats=reduce_network(text)
        self.assertGreater(stats['eliminated_nodes'],0)
        self.assertIn('C1 y 0 1e-12',reduced)
        for f in [0,1e3,1e6,1e9,1e12]:
            np.testing.assert_allclose(port_admittance(text,f),port_admittance(reduced,f),rtol=1e-12,atol=1e-14)

    def test_devices_and_ports_are_protected(self):
        text='.subckt cell a b\nR1 a x 1\nR2 x b 2\nM1 x a b b model\n.ends\n'
        reduced,stats=reduce_network(text)
        self.assertEqual(stats['eliminated_nodes'],0)
        self.assertIn('M1 x a b b model',reduced)

    def test_unsafe_resistors_are_rejected(self):
        for resistance in ['0','-1','nan','1 TC=0.001','rmodel']:
            with self.assertRaises(ValueError):
                reduce_network(f'.subckt cell a b\nR1 a b {resistance}\n.ends\n')
        for device in ['B1 a b I=I(R1)', 'F1 a b R1 2', 'H1 a b R1 2']:
            with self.assertRaises(ValueError):
                reduce_network(f'.subckt cell a b\nR1 a b 2\n{device}\n.ends\n')


if __name__=='__main__':unittest.main()
