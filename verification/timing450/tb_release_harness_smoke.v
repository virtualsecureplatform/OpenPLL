// Boundary/reset elaboration control only; no lock or release claim.
`timescale 1ns/1ps
module tb_release_harness_smoke;
    reg refclk=0, pllout=0, reset_n=0;
    wire tracking, bbpd_reset_n, busy, failed;
    always #20 refclk=~refclk;
    always #1.111 pllout=~pllout;
    IntegerPLL_ReleaseHarness dut (
        .REFCLK(refclk), .PLLOUT(pllout), .RESET_N(reset_n), .PLL_ENABLE(1'b0),
        .MODE_DIVIDER(5'd18), .BBPD(2'b00), .KI(8'd4), .KP(5'd0),
        .TRACKING(tracking), .BBPD_RESET_N(bbpd_reset_n),
        .CONFIG_BUSY(busy), .FAILED(failed), .CLKDIV_RETIMED(),
        .COARSE_CODE(), .DCO_CODE(), .DLF_CODE()
    );
    initial begin
        #10;
        if (tracking !== 0 || bbpd_reset_n !== 0 || busy !== 0)
            $fatal(1,"reset/disable boundary is not inactive");
        #30 reset_n=1;
        #200;
        if (tracking !== 0 || bbpd_reset_n !== 0 || busy !== 0 || failed !== 0)
            $fatal(1,"disabled boundary is not inactive");
        $display("PASS: candidate harness elaborates and remains inactive while disabled; no PLL qualification");
        $finish;
    end
endmodule
