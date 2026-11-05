import unittest
from prepare_prototype_DCO_zero_wire_R import contract
from prepare_prototype_analog_reference import subcircuits
from audit_hierarchical_capacitance import number

class WireContraction(unittest.TestCase):
    def test_exact_port_preserving_C_sum_and_cell_identity(self):
        leaf='.subckt leaf A Z\nX0 Z A 0 0 sky130_fd_pr__nfet_01v8 w=1 l=0.15\n.ends leaf\n'
        text=leaf+'.subckt ring IN OUT\nX1 internal OUT leaf\nR1 IN internal 25\nC1 internal OUT 1f\nC2 IN OUT 2f\nC3 IN internal 4f\n.ends ring\n'
        model,m=contract(text,'ring');parts=subcircuits(model)
        self.assertEqual(parts['leaf'],leaf)
        self.assertIn('X1 IN OUT leaf',parts['ring'])
        caps=[line.split() for line in parts['ring'].splitlines() if line.startswith('C')]
        self.assertEqual(len(caps),1)
        self.assertEqual(number(caps[0][-1]),number('3f'))
        self.assertEqual(m['contracted_wire_resistors'],1)
    def test_rejects_short_between_top_ports(self):
        with self.assertRaises(ValueError):contract('.subckt ring A B\nR1 A B 1\n.ends ring\n','ring')

if __name__=='__main__':unittest.main()
