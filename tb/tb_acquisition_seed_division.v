// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_acquisition_seed_division;
    reg refclk=0, reset_n=0, enable=1;
    reg [4:0] divider=4;
    wire [7:0] seed;
    wire increasing;
    integer trial, low, high, expected, clocks;
    reg [31:0] random_state=32'h19384576;
    IntegerPLL_FrequencyAcquisition dut(
        .REFCLK(refclk),.PLLOUT(1'b0),.RESET_N(reset_n),
        .DCO_RESET_N(reset_n),.PLL_ENABLE(enable),
        .FEEDBACK_DIVIDER(divider),.FINE_CODE(seed),.TUNING_APPLIED(1'b1),
        .FINE_SEED(seed),.FINE_INCREASING(increasing),
        .COARSE_CODE(),.RUN_FINE(),.BUSY(),.FAILED());
    always #20 refclk=~refclk;
    task check_seed;
        input integer lower, upper, descending;
        begin
            @(negedge refclk);
            dut.divider=4;dut.endpoint_window=1000;
            dut.low_count=descending ? upper : lower;
            dut.high_count=descending ? lower : upper;
            dut.state=8; // Enter endpoint selection with a known bracket.
            expected=8+((descending ? upper-4000 : 4000-lower)*239)/(upper-lower);
            if(expected>247) expected=247;
            clocks=0;
            while(dut.state!=9) begin
                @(posedge refclk);#1;
                clocks=clocks+1;
                if(clocks>33) $fatal(1,"seed division did not finish");
            end
            if(clocks!=33 || seed!==expected[7:0] || increasing!==!descending)
                $fatal(1,"seed mismatch low=%0d high=%0d reverse=%0d expected=%0d actual=%0d clocks=%0d",
                       lower,upper,descending,expected,seed,clocks);
        end
    endtask
    initial begin
        #1;reset_n=0;#39;reset_n=1;
        check_seed(3997,4003,0);check_seed(3997,4003,1);
        check_seed(0,65535,0);check_seed(0,65535,1);
        check_seed(3998,65535,0);check_seed(3998,65535,1);
        check_seed(0,4002,0);check_seed(0,4002,1);
        for(trial=0;trial<200;trial=trial+1) begin
            random_state=random_state*32'd1664525+32'd1013904223;
            low=random_state%3999;
            random_state=random_state*32'd1664525+32'd1013904223;
            high=4002+random_state%61534;
            check_seed(low,high,0);check_seed(low,high,1);
        end
        // Withdrawal cancels arithmetic without handing an unfinished seed off.
        @(negedge refclk);dut.divider=4;dut.endpoint_window=1000;
        dut.low_count=3600;dut.high_count=4400;dut.state=8;
        repeat(5) @(negedge refclk);
        enable=0;@(posedge refclk);#1;
        if(dut.state!=0) $fatal(1,"disable did not cancel division");
        enable=1;
        @(negedge refclk);dut.divider=4;dut.endpoint_window=1000;
        dut.low_count=3600;dut.high_count=4400;dut.state=8;
        repeat(5) @(negedge refclk);
        divider=18;@(posedge refclk);#1;
        if(dut.state!=1 || dut.divider!=18)
            $fatal(1,"mode change did not restart acquisition");
        $display("acquisition_seed_division=pass cases=408");$finish;
    end
    initial begin #1000000;$fatal(1,"seed test watchdog");end
endmodule
