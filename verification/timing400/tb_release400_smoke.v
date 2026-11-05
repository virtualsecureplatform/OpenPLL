// Frozen-candidate boundary and divider tests; no acquisition/lock claim.
`timescale 1ns/1ps
module release400_smoke_case #(parameter integer DIVIDER=16)(output reg done=0);
    reg refclk=0, pllout=0, reset_n=0;
    wire tracking, bbpd_reset_n, busy, failed, divided;
    integer input_cycles=0, previous_cycle, j;
    always #20 refclk=~refclk;
    always #(500.0/(25.0*DIVIDER)) pllout=~pllout;
    always @(posedge pllout) input_cycles=input_cycles+1;
    IntegerPLL_ReleaseHarness dut (
        .REFCLK(refclk), .PLLOUT(pllout), .RESET_N(reset_n), .PLL_ENABLE(1'b0),
        .MODE_DIVIDER(DIVIDER[4:0]), .BBPD(2'b00), .KI(8'd4), .KP(5'd0),
        .TRACKING(tracking), .BBPD_RESET_N(bbpd_reset_n),
        .CONFIG_BUSY(busy), .FAILED(failed), .CLKDIV_RETIMED(),
        .COARSE_CODE(), .DCO_CODE(), .DLF_CODE()
    );
    // Match the actual frozen candidate's divider configuration.
    IntegerPLL_MMD_Retimer #(.RATIO_WIDTH(5),.REGISTER_CONFIG(1),
                            .COUNTDOWN(1),.CONFIG_PIPELINE(1)) divider (
        .DIV_IN(pllout),.RESET_N(reset_n),.CLK_DIV_RATIO(DIVIDER[4:0]),
        .CLKDIV_RETIMED(divided)
    );
    initial begin
        #10;
        if (tracking !== 0 || bbpd_reset_n !== 0 || busy !== 0)
            $fatal(1,"reset boundary active for divider %0d",DIVIDER);
        #30 reset_n=1;
        repeat(64) @(posedge pllout);
        if (tracking !== 0 || bbpd_reset_n !== 0 || busy !== 0 || failed !== 0)
            $fatal(1,"disabled boundary active for divider %0d",DIVIDER);
        @(posedge divided); previous_cycle=input_cycles;
        for(j=0;j<12;j=j+1) begin
            @(posedge divided);
            if(input_cycles-previous_cycle != DIVIDER)
                $fatal(1,"wrong divider: expected %0d observed %0d",DIVIDER,input_cycles-previous_cycle);
            previous_cycle=input_cycles;
        end
        $display("PASS: frozen candidate reset/disable and divide%0d, twelve periods",DIVIDER);
        done=1;
    end
endmodule

module tb_release400_smoke;
    wire [3:0] done;
    release400_smoke_case #(4) m100(done[0]);
    release400_smoke_case #(10) m250(done[1]);
    release400_smoke_case #(12) m300(done[2]);
    release400_smoke_case #(16) m400(done[3]);
    initial begin
        wait(&done);
        $display("PASS: all four supported modes; no wholePLL qualification");
        $finish;
    end
    initial begin
        #5000;
        $fatal(1,"smoke timeout");
    end
endmodule
