// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Program once after reset, including when the fine loop is disabled.
// Programming inputs and gains must remain stable until the next reset.
module IntegerPLL_ProgrammedStartup (
    input wire REFCLK, RESET_N, REF_RESET_N, PLL_ENABLE,
    input wire [5:0] STARTUP_COARSE,
    input wire [7:0] STARTUP_FINE,
    input wire STARTUP_INCREASING,
    input wire [7:0] KI,
    input wire [4:0] KP,
    input wire TUNING_APPLIED,
    input wire [7:0] LOADED_FINE,
    output reg [5:0] COARSE_CODE,
    output reg [7:0] FINE_SEED,
    output reg INCREASING,
    output reg [7:0] CONFIGURED_KI,
    output reg [4:0] CONFIGURED_KP,
    output wire OSC_RESET_N, CONFIG_READY, RUN_FINE,
    output wire FAILED
);
    localparam [2:0] CAPTURE=0, SETTLE=1, LOAD=2, READY=3,
                     START=4, RUN=5, FAIL=6;
    reg [2:0] state;
    reg [8:0] wait_count;
    reg [1:0] settle_count;
    wire changed = {STARTUP_COARSE,STARTUP_FINE,STARTUP_INCREASING,KI,KP}
                != {COARSE_CODE,FINE_SEED,INCREASING,CONFIGURED_KI,CONFIGURED_KP};
    assign FAILED = state==FAIL;
    assign OSC_RESET_N = RESET_N && REF_RESET_N && state>=LOAD && state!=FAIL;
    assign CONFIG_READY = state==READY || state==START || state==RUN;
    assign RUN_FINE = PLL_ENABLE && (state==START || state==RUN);

    always @(posedge REFCLK or negedge RESET_N) begin
        if(!RESET_N) begin
            state<=CAPTURE;wait_count<=0;settle_count<=0;
            COARSE_CODE<=0;FINE_SEED<=128;INCREASING<=1;
            CONFIGURED_KI<=0;CONFIGURED_KP<=0;
        end else if(!REF_RESET_N) begin
            state<=CAPTURE;wait_count<=0;settle_count<=0;
        end else if(state!=CAPTURE && changed) begin
            state<=FAIL;
        end else case(state)
            CAPTURE: begin
                // Bounds are hardware checks; X/Z is rejected by the bench.
                if(STARTUP_COARSE>47 || STARTUP_FINE<8 || STARTUP_FINE>247 || KI==0)
                    state<=FAIL;
                else begin
                    COARSE_CODE<=STARTUP_COARSE;FINE_SEED<=STARTUP_FINE;
                    INCREASING<=STARTUP_INCREASING;
                    CONFIGURED_KI<=KI;CONFIGURED_KP<=KP;
                    state<=SETTLE;settle_count<=0;
                end
            end
            SETTLE: begin
                // Two complete reference periods with a stationary preset.
                if(settle_count==1) begin state<=LOAD;wait_count<=0;end
                else settle_count<=settle_count+1'b1;
            end
            LOAD: begin
                if(TUNING_APPLIED && LOADED_FINE==FINE_SEED) begin
                    // Require two reference observations of the loaded seed.
                    if(settle_count==2) begin state<=READY;wait_count<=0;end
                    else settle_count<=2;
                end else begin
                    settle_count<=0;
                    if(wait_count==511) state<=FAIL;
                    else wait_count<=wait_count+1'b1;
                end
            end
            READY: if(PLL_ENABLE) begin state<=START;wait_count<=0;end
            START: begin
                if(!PLL_ENABLE) begin
                    state<=LOAD;wait_count<=0;settle_count<=0;
                end
                else if(TUNING_APPLIED) begin state<=RUN;wait_count<=0;end
                else if(wait_count==511) state<=FAIL;
                else wait_count<=wait_count+1'b1;
            end
            RUN: if(!PLL_ENABLE) begin state<=LOAD;wait_count<=0;settle_count<=0;end
            FAIL: state<=FAIL;
            default: state<=FAIL;
        endcase
    end
endmodule
`default_nettype wire
