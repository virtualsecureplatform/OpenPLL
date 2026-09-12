// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// One outstanding bundled-data transfer. The source holds payload until the
// acknowledgement returns. The destination acknowledges only after its consumer
// has had APPLY_CYCLES clocks to load the tuning registers. Physical constraints
// must bound the payload path relative to the synchronized request path.
module IntegerPLL_TuningHandoff #(
    parameter integer WIDTH=16,
    parameter integer APPLY_CYCLES=3
) (
    input wire REFCLK, DCOCLK,
    input wire REF_RESET_N, DCO_RESET_N,
    input wire [WIDTH-1:0] COMMAND,
    output reg [WIDTH-1:0] APPLIED_COMMAND,
    output wire APPLIED
);
    localparam integer COUNT_WIDTH=$clog2(APPLY_CYCLES+1);
    reg [WIDTH-1:0] payload;
    reg request, acknowledge, sent_valid;
    (* ASYNC_REG="TRUE" *) reg request_meta, request_sync;
    (* ASYNC_REG="TRUE" *) reg acknowledge_meta, acknowledge_sync;
    reg [COUNT_WIDTH-1:0] remaining;
    reg pending_request;
    assign APPLIED=sent_valid && acknowledge_sync==request && payload==COMMAND;

    always @(posedge REFCLK or negedge REF_RESET_N) begin
        if(!REF_RESET_N) begin
            payload<=0; request<=0; sent_valid<=0;
            acknowledge_meta<=0; acknowledge_sync<=0;
        end else begin
            acknowledge_meta<=acknowledge; acknowledge_sync<=acknowledge_meta;
            if(acknowledge_sync==request && (!sent_valid || payload!=COMMAND)) begin
                payload<=COMMAND; request<=!request; sent_valid<=1;
            end
        end
    end
    always @(posedge DCOCLK or negedge DCO_RESET_N) begin
        if(!DCO_RESET_N) begin
            request_meta<=0; request_sync<=0; acknowledge<=0;
            APPLIED_COMMAND<=0; remaining<=0; pending_request<=0;
        end else begin
            request_meta<=request; request_sync<=request_meta;
            if(remaining!=0) begin
                remaining<=remaining-1'b1;
                if(remaining==1) acknowledge<=pending_request;
            end else if(request_sync!=acknowledge) begin
                APPLIED_COMMAND<=payload;
                pending_request<=request_sync;
                remaining<=APPLY_CYCLES[COUNT_WIDTH-1:0];
            end
        end
    end
    // Both domain resets must assert together; release may occur independently.
    // synthesis translate_off
    initial if(WIDTH<1 || APPLY_CYCLES<1) $fatal(1,"invalid handoff parameters");
    // synthesis translate_on
endmodule
`default_nettype wire
