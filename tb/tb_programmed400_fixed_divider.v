`timescale 1ns/1ps
// Exercise the programmed regression while checking every enabled divider edge,
// including the first pulse after reset, before CONFIG_READY and TRACKING.
module tb_programmed400_fixed_divider;
    tb_programmed400 base();
    integer fast_edges=0, last_edge=0, checked_half_cycles=0;
    reg seen_edge=0;
    always @(posedge base.pllout) fast_edges=fast_edges+1;
    always @(negedge base.oscillator_reset_n or negedge base.reset_n)
        seen_edge=0;
    always @(base.divided) begin
        if(base.reset_n && base.oscillator_reset_n &&
           base.dut.core.fast_reset_n && (base.divided===0 || base.divided===1)) begin
            if(seen_edge) begin
                if(fast_edges-last_edge!=8)
                    $fatal(1,"fixed divider half-cycle=%0d fast clocks; expected 8",fast_edges-last_edge);
                checked_half_cycles=checked_half_cycles+1;
            end
            // The first observed rising edge starts the first measured pulse.
            if(base.divided===1 || seen_edge) begin
                seen_edge=1;
                last_edge=fast_edges;
            end
        end
    end
    final begin
        if(checked_half_cycles<100)
            $error("insufficient fixed divider edge coverage: %0d",checked_half_cycles);
        else $display("PASS: fixed divider first-pulse and half-cycle checks=%0d",checked_half_cycles);
    end
endmodule
