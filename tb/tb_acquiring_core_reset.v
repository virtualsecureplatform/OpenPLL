// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_acquiring_core_reset;
    reg refclk=0, dco=0, reset_n=1, running=1;
    wire divided, tracking;
    wire [7:0] code;
    integer trial, fine_edges=0, releases=0;
    IntegerPLL_AcquiringCore dut(
        .REFCLK(refclk),.PLLOUT(dco),.RESET_N(reset_n),.PLL_ENABLE(1'b0),
        .FEEDBACK_DIVIDER(5'd4),.BBPD(2'b00),.KI(8'd0),.KP(5'd0),
        .CLKDIV_RETIMED(divided),.DCO_CODE(code),.TRACKING(tracking));
    always #20 refclk=~refclk;
    always #1.111 if(running) dco=~dco;
    always @(posedge divided or negedge reset_n)
        if(!reset_n) fine_edges=0;
        else fine_edges=fine_edges+1;
    always @(posedge dut.fine_reset_n) begin
        #0.001;
        if(fine_edges!=2 || !reset_n || dut.core.dlf_reset_n!==dut.fine_reset_n)
            $fatal(1,"fine reset must release on second local edge, edges=%0d",fine_edges);
        releases=releases+1;
    end
    task assert_reset;
        begin
            reset_n=0;#0.001;
            if(code!==0 || divided!==0 || tracking!==0 || dut.fine_reset_n!==0)
                $fatal(1,"fine reset did not assert asynchronously");
        end
    endtask
    initial begin
        for(trial=0;trial<32;trial=trial+1) begin
            #(0.1+trial*0.031);assert_reset();
            #15;reset_n=1;
            wait(dut.fine_reset_n);#20;
            running=0;#3;assert_reset();
            #7;reset_n=1;#25;
            if(dut.fine_reset_n!==0 || code!==0 || tracking!==0 || fine_edges!=0)
                $fatal(1,"fine reset released while oscillator stopped");
            running=1;wait(dut.fine_reset_n);#20;
        end
        if(releases!=64) $fatal(1,"missing reset releases");
        $display("acquiring_core_reset=pass releases=64 stopped_clock_cases=32");
        $finish;
    end
    initial begin #20000;$fatal(1,"reset watchdog");end
endmodule
