`timescale 1ns/1ps
// Exercise disable during START, before RUN acknowledges the new command.
module tb_programmed_startup_early_disable;
    reg clk=0, reset_n=0, enabled=0, applied=1;
    wire ready, run_fine, failed, oscillator_reset;
    wire [5:0] coarse;
    wire [7:0] seed, configured_ki;
    wire [4:0] configured_kp;
    wire increasing;
    integer clocks;
    always #20 clk=~clk;
    IntegerPLL_ProgrammedStartup dut(
        .REFCLK(clk), .RESET_N(reset_n), .REF_RESET_N(reset_n),
        .PLL_ENABLE(enabled), .STARTUP_COARSE(6'd1), .STARTUP_FINE(8'd128),
        .STARTUP_INCREASING(1'b1), .KI(8'd4), .KP(5'd0),
        .TUNING_APPLIED(applied), .LOADED_FINE(8'd128),
        .COARSE_CODE(coarse), .FINE_SEED(seed), .INCREASING(increasing),
        .CONFIGURED_KI(configured_ki), .CONFIGURED_KP(configured_kp),
        .OSC_RESET_N(oscillator_reset), .CONFIG_READY(ready),
        .RUN_FINE(run_fine), .FAILED(failed));
    initial begin
        #1 reset_n=0;
        repeat(2) @(negedge clk);
        reset_n=1;
        clocks=0;
        while(!ready && !failed && clocks<20) begin
            @(negedge clk);clocks=clocks+1;
        end
        if(!ready || failed) $fatal(1,"initial seed confirmation failed");
        enabled=1;
        @(negedge clk);
        if(!run_fine || !ready) $fatal(1,"START was not reached");
        enabled=0;
        @(negedge clk);
        if(run_fine || ready || failed) $fatal(1,"withdrawal did not return to LOAD");
        // Both observations must belong to this LOAD visit. The initial
        // startup's confirmation must not satisfy the re-enable handshake.
        @(negedge clk);
        if(ready || failed) $fatal(1,"ready after only one reloaded-seed observation");
        @(negedge clk);
        if(!ready || failed) $fatal(1,"two seed observations did not restore ready");
        enabled=1;
        repeat(3) @(negedge clk);
        if(!ready || !run_fine || failed) $fatal(1,"restart failed");
        $display("PASS: early START disable requires two new seed observations");
        $finish;
    end
    initial begin #10000;$fatal(1,"test timeout");end
endmodule
