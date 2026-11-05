`timescale 1ns/1ps
module tb_timing450_graydecode;
    reg refclk=0, reset_n=1;
    reg [15:0] injected_gray=0;
    integer value;
    reg [15:0] previous=0;
    IntegerPLL_FrequencyAcquisition dut(
        .REFCLK(refclk),.PLLOUT(1'b0),.RESET_N(reset_n),.DCO_RESET_N(reset_n),
        .PLL_ENABLE(1'b0),.FEEDBACK_DIVIDER(5'd18),.FINE_CODE(8'd128),
        .TUNING_APPLIED(1'b1),.FINECLK(1'b0),.FINE_RESET_N(reset_n),
        .COARSE_CODE(),.FINE_SEED(),.FINE_INCREASING(),.RUN_FINE(),.BUSY(),.FAILED());
    initial begin
        #1;reset_n=0;#1;reset_n=1;
        force dut.gray_meta=injected_gray;
        for(value=0;value<65536;value=value+1) begin
            injected_gray=value^(value>>1);
            #1;refclk=1;#1;
            if(dut.gray_sync!==injected_gray || dut.synchronized_count!==previous)
                $fatal(1,"registered Gray decode mismatch value=%0d count=%0d expected=%0d",value,dut.synchronized_count,previous);
            previous=value;refclk=0;
        end
        // Flush the last value, including the full 16-bit wrap boundary.
        injected_gray=0;#1;refclk=1;#1;
        if(dut.synchronized_count!==16'hffff) $fatal(1,"lost pre-wrap count");
        refclk=0;#1;refclk=1;#1;
        if(dut.synchronized_count!==0) $fatal(1,"lost wrapped count");
        reset_n=0;#1;
        if(dut.synchronized_count!==0) $fatal(1,"decode reset failed");
        $display("timing450_graydecode=pass values=65536 latency=1");$finish;
    end
endmodule

module tb_timing450_scanstage;
    reg refclk=0, reset_n=1, enable=1;
    reg [4:0] divider=18;
    reg [15:0] injected_count=0;
    IntegerPLL_FrequencyAcquisition dut(
        .REFCLK(refclk),.PLLOUT(1'b0),.RESET_N(reset_n),.DCO_RESET_N(reset_n),
        .PLL_ENABLE(enable),.FEEDBACK_DIVIDER(divider),.FINE_CODE(8'd128),
        .TUNING_APPLIED(1'b1),.FINECLK(1'b0),.FINE_RESET_N(reset_n),
        .COARSE_CODE(),.FINE_SEED(),.FINE_INCREASING(),.RUN_FINE(),.BUSY(),.FAILED());
    task edge_ref;
        begin #1;refclk=1;#1;refclk=0;end
    endtask
    task measurement;
        input integer edges, band;
        reg [15:0] old_best;
        begin
            injected_count=1000+edges;
            dut.divider=18;dut.state=2;dut.cycles=31;
            dut.COARSE_CODE=band;dut.start_count=1000;
            old_best=dut.best_error[0];edge_ref;
            if(dut.best_error[0]!==old_best || dut.state!==13)
                $fatal(1,"scan ranking bypassed capture stage");
            edge_ref;
        end
    endtask
    initial begin
        #1;reset_n=0;#1;reset_n=1;
        force dut.synchronized_count=injected_count;
        measurement(500,10);measurement(600,11);measurement(580,12);
        if(dut.best_error[0]!==4 || dut.best_error[1]!==24 || dut.best_error[2]!==76 ||
           dut.best_band[0]!==12 || dut.best_band[1]!==11 || dut.best_band[2]!==10)
            $fatal(1,"independent candidate ranking mismatch");
        // A mode change cancels a captured result before it reaches ranking.
        dut.state=13;dut.scan_elapsed=576;divider=4;edge_ref;
        if(dut.state!==1 || dut.divider!==4 || dut.best_error[0]!==16'hffff)
            $fatal(1,"stale scan result survived mode change");
        dut.state=13;enable=0;edge_ref;
        if(dut.state!==0) $fatal(1,"disable did not cancel scan evaluation");
        $display("timing450_scanstage=pass ranking_and_cancellation");$finish;
    end
endmodule
