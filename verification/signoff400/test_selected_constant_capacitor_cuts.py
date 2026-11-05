import unittest
from eliminate_selected_constant_capacitor_cuts import transform

class ConstantCapacitorCutsTest(unittest.TestCase):
    def test_only_constant_capacitor_only_unobserved_nodes_are_removed(self):
        devices='C1 x quiet 1e-12\nC2 x observed 2e-12\nC3 x resistive 3e-12\nR1 resistive x 10\nX1 nonlinear x 0 0 fet\nC4 x nonlinear 4e-12\nC5 x moving 5e-12\n'
        sources='V1 quiet 0 1.8\nV2 observed 0 .7\nV3 resistive 0 1.8\nV4 nonlinear 0 1.8\nV5 moving 0 PULSE(0 1 1n 1p 1p 1n 2n)\n'
        result,src,record=transform(devices,sources,['observed'])
        self.assertEqual(set(record['eliminated_constant_nodes']),{'quiet'})
        self.assertIn('C1 x 0 1e-12',result);self.assertNotIn('V1 quiet',src)
        for line in devices.splitlines()[1:]:self.assertIn(line,result)
        # Constant offsets cancel in a charge difference at every retained v.
        for a,b in [(.1,1.7),(1.8,0),(-.03,1.83)]:
            self.assertAlmostEqual(1e-12*((b-1.8)-(a-1.8)),1e-12*(b-a),places=24)

    def test_nonlinear_capacitance_ic_and_current_references_protect_nodes(self):
        for device,deck in [('C1 x q {f(V(q))}\n',''),('C1 x q 1e-12 IC=1\n',''),('C1 x q 1e-12\n','.print tran I(Vq)\n')]:
            _,_,record=transform(device,'Vq q 0 1.8\n',[],deck)
            self.assertEqual(record['eliminated_constant_nodes'],{})

if __name__=='__main__':unittest.main()
