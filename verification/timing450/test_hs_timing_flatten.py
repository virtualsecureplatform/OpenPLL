import unittest
from flatten_hs_timing_cells import flatten

class FlattenHSTiming(unittest.TestCase):
    def example(self):
        return '''module sky130_fd_sc_hs__x(A,X,VPWR,VGND);
input A;
output X;
input VPWR;
input VGND;
wire internal;
buf (X,A);
specify
(A => X) = (0,0);
$width(posedge A,1,0,notifier);
endspecify
endmodule
module sky130_fd_sc_hs__x_1(A,X);
input A;
output X;
supply1 VPWR;
supply0 VGND;
sky130_fd_sc_hs__x base (.A(A),.X(X),.VPWR(VPWR),.VGND(VGND));
endmodule
'''
    def test_paths_checks_and_supplies_at_owning_cell(self):
        text,changes=flatten(self.example());wrapper=text.split('module sky130_fd_sc_hs__x_1')[1]
        self.assertIn('(A => X)',wrapper)
        self.assertIn('$width',wrapper)
        self.assertIn('supply1 VPWR;',wrapper)
        self.assertNotIn('base (',wrapper)
        self.assertEqual(len(changes),1)
    def test_remapping_and_conditional_input_rejected(self):
        for text in (self.example().replace('.A(A)','.A(other)'), '`ifdef FUNCTIONAL\n'+self.example(),
                     self.example().replace('.VGND(VGND)',''), self.example().replace('input VGND;','')):
            with self.assertRaises(RuntimeError):flatten(text)

if __name__=='__main__':unittest.main()
