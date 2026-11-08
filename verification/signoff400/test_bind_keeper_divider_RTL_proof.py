import unittest
from bind_keeper_divider_RTL_proof import configuration
class Binding(unittest.TestCase):
    def fixture(self):
        top='IntegerPLL_ProgrammedCore digital ();'
        programmed="localparam [4:0] FEEDBACK_DIVIDER=5'd16; .MMD_REGISTER_CONFIG(0), .MMD_RATIO_WIDTH(5), .MMD_COUNTDOWN(1), .MMD_CONFIG_PIPELINE(0), .MMDCLKDIV_RATIO({3'b000,FEEDBACK_DIVIDER})"
        digital='.RATIO_WIDTH(MMD_RATIO_WIDTH), .REGISTER_CONFIG(MMD_REGISTER_CONFIG), .COUNTDOWN(MMD_COUNTDOWN), .CONFIG_PIPELINE(MMD_CONFIG_PIPELINE), .CLK_DIV_RATIO(MMDCLKDIV_RATIO[MMD_RATIO_WIDTH-1:0])'
        return [top,programmed,digital]
    def test_current_declarations(self):self.assertEqual(configuration(*self.fixture())['ratio'],16)
    def test_ratio_and_pipeline_changes_rejected(self):
        for before,after in [("5'd16","5'd15"),('MMD_CONFIG_PIPELINE(0)','MMD_CONFIG_PIPELINE(1)')]:
            a=self.fixture();a[1]=a[1].replace(before,after)
            with self.assertRaisesRegex(ValueError,'configuration'):configuration(*a)
    def test_forwarding_change_rejected(self):
        a=self.fixture();a[2]=a[2].replace('.COUNTDOWN(MMD_COUNTDOWN)','.COUNTDOWN(0)')
        with self.assertRaisesRegex(ValueError,'configuration'):configuration(*a)
if __name__=='__main__':unittest.main()
