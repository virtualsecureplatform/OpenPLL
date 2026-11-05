// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_acquisition_rail_clock;
    reg pll=0,refclk=0,fine=0,reset_n=1,fine_reset_n=1;
    reg [7:0] code=128;
    reg expected=0;
    integer samples=0,changes;
    IntegerPLL_FrequencyAcquisition #(.FINE_CODE_ON_FINECLK(1)) dut(
        .REFCLK(refclk),.PLLOUT(pll),.RESET_N(reset_n),.DCO_RESET_N(reset_n),
        .FINECLK(fine),.FINE_RESET_N(fine_reset_n),.PLL_ENABLE(1'b0),
        .FEEDBACK_DIVIDER(5'd18),.FINE_CODE(code),.TUNING_APPLIED(1'b0),
        .COARSE_CODE(),.FINE_SEED(),.FINE_INCREASING(),.RUN_FINE(),.BUSY(),.FAILED());
    always #1.111 pll=~pll;
    always #20 refclk=~refclk;
    initial begin #7.3;forever #20 fine=~fine;end
    always @(posedge fine or negedge fine_reset_n)
        if(!fine_reset_n) expected<=0;
        else begin expected<=code==0 || code==255;samples=samples+1;end
    always @(negedge pll) begin
        #0.001;
        if(dut.dco_rail!==expected) $fatal(1,"rail flag changed outside owning clock");
    end
    initial begin
        #0.1;reset_n=0;fine_reset_n=0;#4;reset_n=1;fine_reset_n=1;
        for(changes=0;changes<2048;changes=changes+1) begin
            @(negedge pll);#0.01;
            case(changes%4) 0:code=0;1:code=128;2:code=255;3:code=129;endcase
            if(changes%127==0) begin
                #0.2;fine_reset_n=0;#0.001;
                if(dut.dco_rail!==0) $fatal(1,"fine reset did not clear rail");
                #0.2;fine_reset_n=1;
            end
        end
        if(samples<100) $fatal(1,"insufficient fine samples");
        $display("acquisition_rail_clock=pass changes=%0d fine_samples=%0d",changes,samples);
        $finish;
    end
endmodule
