`timescale 1ns/1ps
// Establish one observable phase-acquisition challenge on each tracking entry.
// The controller and oscillator run normally. Only the external reference is
// delayed; no DUT storage or feedback clock is forced. The reference returns
// to a 40 ns period after the initial alignment interval.
module Prototype400ReferencePhase(
    input wire TRACKING, FEEDBACK_PHYSICAL,
    input integer PHASE_NS,
    output reg REFCLK=0
);
    reg pending=0;
    integer epoch=0;
    realtime feedback_at;
    always @(posedge TRACKING) begin
        if(pending) $fatal(1,"overlapping reference phase requests");
        pending=1;
    end
    initial begin
        forever begin
            #20;
            if(pending) begin
                pending=0;
                // Preserve a full low interval before the aligned rising edge.
                REFCLK=0;
                #20;
                @(posedge FEEDBACK_PHYSICAL);
                feedback_at=$realtime;
                #(PHASE_NS);
                REFCLK=1;
                $display("REFERENCE_PHASE_INITIALIZED epoch=%0d feedback_ns=%.9f reference_ns=%.9f offset_ns=%0d",
                    epoch,feedback_at,$realtime,PHASE_NS);
                epoch=epoch+1;
            end else REFCLK=~REFCLK;
        end
    end
endmodule
