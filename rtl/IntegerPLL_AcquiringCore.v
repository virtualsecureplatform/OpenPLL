// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental integration boundary for acquisition and the real digital core.
// Gains remain explicit until characterized tables qualify for production.
module IntegerPLL_AcquiringCore (
    input wire REFCLK, PLLOUT, RESET_N, PLL_ENABLE,
    input wire [4:0] FEEDBACK_DIVIDER,
    input wire [1:0] BBPD,
    input wire [7:0] KI,
    input wire [4:0] KP,
    output wire CLKDIV_RETIMED, BBPD_RESET_N, TRACKING, CONFIG_BUSY, FAILED,
    output wire [5:0] COARSE_CODE,
    output wire [7:0] DCO_CODE,
    output wire [9:0] DLF_CODE,
    output wire [46:0] COARSETHERMAL_CODE,
    output wire [254:0] DCO_THERM
);
    (* ASYNC_REG="TRUE" *) reg [1:0] ref_reset_pipe, dco_reset_pipe;
    always @(posedge REFCLK or negedge RESET_N)
        if(!RESET_N) ref_reset_pipe<=0;
        else ref_reset_pipe<={ref_reset_pipe[0],1'b1};
    always @(posedge PLLOUT or negedge RESET_N)
        if(!RESET_N) dco_reset_pipe<=0;
        else dco_reset_pipe<={dco_reset_pipe[0],1'b1};
    wire ref_reset_n=ref_reset_pipe[1];
    wire dco_reset_n=dco_reset_pipe[1];
    wire run_fine, increasing, applied;
    wire [7:0] seed;
    wire [33:0] command={COARSE_CODE,seed,increasing,FEEDBACK_DIVIDER,run_fine,KI,KP};
    wire [33:0] local_command;
    wire [5:0] local_coarse;
    wire [7:0] local_seed, local_ki;
    wire [4:0] local_divider, local_kp;
    wire local_increasing, local_run;
    // Legacy core observability outputs are intentionally unused at this boundary.
    /* verilator lint_off PINCONNECTEMPTY */
    assign {local_coarse,local_seed,local_increasing,local_divider,local_run,local_ki,local_kp}=local_command;
    IntegerPLL_TuningHandoff #(.WIDTH(34),.APPLY_CYCLES(3)) handoff(
        .REFCLK(REFCLK),.DCOCLK(PLLOUT),.REF_RESET_N(ref_reset_n),
        .DCO_RESET_N(dco_reset_n),.COMMAND(command),
        .APPLIED_COMMAND(local_command),.APPLIED(applied));
    IntegerPLL_FrequencyAcquisition acquisition(
        .REFCLK(REFCLK),.PLLOUT(PLLOUT),.RESET_N(ref_reset_n),
        .DCO_RESET_N(dco_reset_n),
        .PLL_ENABLE(PLL_ENABLE),.FEEDBACK_DIVIDER(FEEDBACK_DIVIDER),
        .FINE_CODE(DCO_CODE),.TUNING_APPLIED(applied),.COARSE_CODE(COARSE_CODE),
        .FINE_SEED(seed),.FINE_INCREASING(increasing),.RUN_FINE(run_fine),
        .BUSY(),.FAILED(FAILED));

    // Withdrawal asserts immediately, even if PLLOUT stops. Release takes two
    // DCO clocks after the stable bundle has reached the destination.
    wire track_reset_n=dco_reset_n && run_fine && local_run &&
                       local_coarse==COARSE_CODE;
    (* ASYNC_REG="TRUE" *) reg [1:0] track_pipe;
    always @(posedge PLLOUT or negedge track_reset_n)
        if(!track_reset_n) track_pipe<=0;
        else track_pipe<={track_pipe[0],1'b1};
    assign TRACKING=track_pipe[1];
    assign BBPD_RESET_N=TRACKING;
    assign CONFIG_BUSY=PLL_ENABLE && !TRACKING;

    IntegerPLL_DigitalCore #(.DLF_FRAC_WIDTH(2),.DLF_PROP_RAIL_GUARD(1),
        .DLF_UPDATE_ON_PLLOUT(1)) core(
        .PLLOUT(PLLOUT),.RESET_N(dco_reset_n),.BBPD(BBPD),
        .DLF_En(TRACKING),.DLF_Clear(!TRACKING),.DLF_Ext_Override(1'b0),
        .DLF_IN_POL(local_increasing),.DLF_Ext_Data({local_seed,2'b00}),
        .DLF_KI(local_ki),.DLF_KP(local_kp),
        // The reference-owned coarse code can restart an oscillator that is
        // too slow or stopped; acquisition waits for the seed acknowledgement.
        .COARSEBINARY_CODE(COARSE_CODE),.MMDCLKDIV_RATIO({3'b000,local_divider}),
        .CLKDIV_RETIMED(CLKDIV_RETIMED),.DCO_CODE(DCO_CODE),.DLF_CODE(DLF_CODE),
        .COARSETHERMAL_CODE(COARSETHERMAL_CODE),.DCO_THERM(DCO_THERM),
        .PLLOUT_DIV(),.Medium_BINARY_CODE(),.Fine_BINARY_CODE(),
        .Medium_CAPS_CTRL(),.Fine_CAPS_CTRL());
    /* verilator lint_on PINCONNECTEMPTY */
endmodule
`default_nettype wire
