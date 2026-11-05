import unittest
from normalize_hs_timing_views import normalize

class HSTimingViews(unittest.TestCase):
    def test_repairs_declared_aliases_and_keeps_checks(self):
        text='''module example (CLK,D);
wire RESET_B_delayed;
wire CLK_delayed;
wire cond0;
wire awake;
wire 1;
assign cond0 = awake;
specify
$recrem(posedge RESET_B,posedge CLK,0,0,notifier,AWAKE,AWAKE,RESETB_delayed,CLK_delayed);
$setuphold(posedge CLK,posedge D,0,0,notifier,COND0,COND0,CLK_delayed,D_delayed);
endspecify
endmodule
'''
        fixed,changes=normalize(text)
        self.assertNotIn('wire 1;',fixed)
        self.assertIn('notifier,awake,awake,RESET_B_delayed',fixed)
        self.assertIn('$setuphold',fixed)
        self.assertEqual(fixed.count('$'),text.count('$'))
        self.assertTrue(changes)
    def test_unknown_alias_target_rejected(self):
        with self.assertRaises(RuntimeError):normalize('module x();\n$width(posedge CLK &&& COND0,1,0,notifier);\nendmodule\n')
    def test_does_not_change_unrelated_behavior(self):
        text='module x();\nwire 1;\nwire AWAKE;\nassign AWAKE = a && b;\nendmodule\n'
        fixed,_=normalize(text)
        self.assertIn('assign AWAKE = a && b;',fixed)
        with self.assertRaises(RuntimeError):normalize('module x();\nassign q = d;\nendmodule\n')

if __name__=='__main__':unittest.main()
