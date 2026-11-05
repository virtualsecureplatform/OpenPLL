// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_acquisition_edge_counter;
    reg dco=0, reset_n=1;
    reg [15:0] expected=0, previous_gray=0;
    integer cycle;
    reg [15:0] changed;
    IntegerPLL_FrequencyAcquisition dut(
        .REFCLK(1'b0),.PLLOUT(dco),.RESET_N(reset_n),
        .DCO_RESET_N(reset_n),.PLL_ENABLE(1'b0),.FEEDBACK_DIVIDER(5'd18),
        .FINE_CODE(8'd128),.TUNING_APPLIED(1'b1),.COARSE_CODE(),
        .FINE_SEED(),.FINE_INCREASING(),.RUN_FINE(),.BUSY(),.FAILED());
    always #1.111 dco=~dco;
    initial begin
        #0.1;reset_n=0;#0.1;reset_n=1;
        for(cycle=0;cycle<150000;cycle=cycle+1) begin
            @(posedge dco);expected=expected+16'd1;#0.001;
            if(dut.dco_count!==expected || dut.dco_gray!==((expected>>1)^expected))
                $fatal(1,"counter/Gray mismatch cycle=%0d expected=%0d actual=%0d",
                       cycle,expected,dut.dco_count);
            changed=previous_gray^dut.dco_gray;
            if(changed==0 || (changed&(changed-16'd1))!=0)
                $fatal(1,"Gray bus changed more than one bit");
            previous_gray=dut.dco_gray;
            // Assert reset while carry predictions are active, including
            // just before an upper-nibble rollover.
            if(cycle==14 || cycle==4109 || cycle==75000) begin
                @(negedge dco);reset_n=0;#0.001;
                if(dut.dco_count!==0 || dut.dco_gray!==0 ||
                   dut.carry4!==0 || dut.carry8!==0 || dut.carry12!==0)
                    $fatal(1,"reset did not clear counter carry state");
                expected=0;previous_gray=0;reset_n=1;
            end
        end
        $display("acquisition_edge_counter=pass cycles=150000");$finish;
    end
    initial begin #400000;$fatal(1,"counter watchdog");end
endmodule
