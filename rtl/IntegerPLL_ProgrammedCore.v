// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Programmed 400 MHz prototype boundary. Settings are static until reset.
// TRACKING is a loop-enable indication, never a lock detector.
module IntegerPLL_ProgrammedCore #(
    // The fine loop updates once per feedback period. Keep its arithmetic
    // on that clock rather than requiring it to close at the oscillator rate.
    parameter integer DLF_UPDATE_ON_PLLOUT = 0
) (
    input wire REFCLK, PLLOUT, RESET_N, PLL_ENABLE,
    input wire [5:0] STARTUP_COARSE,
    input wire [7:0] STARTUP_FINE,
    input wire STARTUP_INCREASING,
    output wire OSC_RESET_N, CONFIG_READY,
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
    localparam [4:0] FEEDBACK_DIVIDER = 5'd16;
    wire oscillator_reset_n;
    wire [7:0] core_dco_code;
    wire [254:0] core_dco_therm;
    wire [46:0] core_coarse_therm;
    wire [7:0] startup_seed;
    wire [7:0] configured_ki;
    wire [4:0] configured_kp;
    wire configured_increasing;
    wire config_ready;
    assign OSC_RESET_N = oscillator_reset_n;
    assign CONFIG_READY = config_ready;
    // An independent preset decoder breaks the stopped-clock bootstrap cycle.
    // Handoff to the core occurs only after its registered seed has loaded.
    assign DCO_CODE = (config_ready && PLL_ENABLE && !FAILED) ? core_dco_code : startup_seed;
    wire [254:0] startup_therm;
    IntegerPLL_B2TH #(.BIN_WIDTH(8),.THERM_WIDTH(255),.INVERT_OUTPUT(1))
        startup_fine_decoder(.binary_code(startup_seed),.thermal_code(startup_therm));
    assign DCO_THERM = (config_ready && PLL_ENABLE && !FAILED) ? core_dco_therm : startup_therm;
    assign COARSETHERMAL_CODE = core_coarse_therm;
    (* ASYNC_REG="TRUE" *) reg [1:0] ref_reset_pipe, dco_reset_pipe;
    always @(posedge REFCLK or negedge RESET_N)
        if(!RESET_N) ref_reset_pipe<=0;
        else ref_reset_pipe<={ref_reset_pipe[0],1'b1};
    always @(posedge PLLOUT or negedge RESET_N)
        if(!RESET_N) dco_reset_pipe<=0;
        else dco_reset_pipe<={dco_reset_pipe[0],1'b1};
    wire ref_reset_n=ref_reset_pipe[1];
    wire dco_reset_n=dco_reset_pipe[1];
    wire fine_reset_n;
    wire run_fine, increasing, applied, fast_applied, fine_applied;
    wire [7:0] seed;
    wire [33:0] command={COARSE_CODE,seed,increasing,FEEDBACK_DIVIDER,run_fine,configured_ki,configured_kp};
    wire [33:0] local_command;
    wire [33:0] fine_command;
    wire [7:0] fine_seed=fine_command[27:20];
    wire fine_increasing=fine_command[19];
    wire [7:0] fine_ki=fine_command[12:5];
    wire [4:0] fine_kp=fine_command[4:0];
    assign applied=fast_applied && fine_applied;
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
        .APPLIED_COMMAND(local_command),.APPLIED(fast_applied));
    generate
        if(DLF_UPDATE_ON_PLLOUT==0) begin : gen_feedback_handoff
            (* ASYNC_REG="TRUE" *) reg [1:0] reset_pipe;
            // Each domain releases the external reset on its own clock.
            // The fast-domain release must not drive fine-domain storage.
            always @(posedge CLKDIV_RETIMED or negedge RESET_N)
                if(!RESET_N) reset_pipe<=0;
                else reset_pipe<={reset_pipe[0],1'b1};
            assign fine_reset_n=reset_pipe[1];
            // A fast-domain acknowledgement cannot prove that a slow-clock
            // consumer has loaded its seed. Deliver and acknowledge the fine
            // bundle on its own clock, with a separate payload timing bound.
            IntegerPLL_TuningHandoff #(.WIDTH(34),.APPLY_CYCLES(3)) fine_handoff(
                .REFCLK(REFCLK),.DCOCLK(CLKDIV_RETIMED),
                .REF_RESET_N(ref_reset_n),.DCO_RESET_N(reset_pipe[1]),
                .COMMAND(command),.APPLIED_COMMAND(fine_command),.APPLIED(fine_applied));
        end else begin : gen_fast_handoff
            assign fine_reset_n=dco_reset_n;
            assign fine_command=local_command;
            assign fine_applied=1'b1;
        end
    endgenerate
    assign seed = startup_seed;
    assign increasing = configured_increasing;
    IntegerPLL_ProgrammedStartup startup (
        .REFCLK(REFCLK),.RESET_N(RESET_N),.REF_RESET_N(ref_reset_n),
        .PLL_ENABLE(PLL_ENABLE),.STARTUP_COARSE(STARTUP_COARSE),
        .STARTUP_FINE(STARTUP_FINE),.STARTUP_INCREASING(STARTUP_INCREASING),
        .KI(KI),.KP(KP),.TUNING_APPLIED(applied),.LOADED_FINE(core_dco_code),
        .COARSE_CODE(COARSE_CODE),.FINE_SEED(startup_seed),
        .INCREASING(configured_increasing),.CONFIGURED_KI(configured_ki),
        .CONFIGURED_KP(configured_kp),.OSC_RESET_N(oscillator_reset_n),
        .CONFIG_READY(config_ready),.RUN_FINE(run_fine),.FAILED(FAILED));

    // Withdrawal asserts immediately, even if PLLOUT stops. Release takes two
    // DCO clocks after the stable bundle has reached the destination.
    // RUN_FINE rises only after LOAD has acknowledged the complete bundle.
    // Any mode/coarse change withdraws RUN_FINE before another transfer.
    wire track_reset_n=dco_reset_n && run_fine && local_run && PLL_ENABLE && !FAILED;
    (* ASYNC_REG="TRUE" *) reg [1:0] track_pipe;
    always @(posedge PLLOUT or negedge track_reset_n)
        if(!track_reset_n) track_pipe<=0;
        else track_pipe<={track_pipe[0],1'b1};
    generate
        if(DLF_UPDATE_ON_PLLOUT==0) begin : gen_feedback_tracking
            // Validate the fine bundle in its own domain. Its comparison
            // must not drive the fast-domain reset synchronizer.
            wire fine_track_reset_n=fine_reset_n && run_fine && PLL_ENABLE && !FAILED &&
                 fine_command[13] && fine_command[33:28]==COARSE_CODE;
            (* ASYNC_REG="TRUE" *) reg [1:0] release_pipe;
            always @(posedge CLKDIV_RETIMED or negedge fine_track_reset_n)
                if(!fine_track_reset_n) release_pipe<=0;
                else release_pipe<={release_pipe[0],track_pipe[1]};
            assign TRACKING=release_pipe[1] && fine_track_reset_n;
        end else begin : gen_fast_tracking
            assign TRACKING=track_pipe[1] && track_reset_n;
        end
    endgenerate
    assign BBPD_RESET_N=TRACKING;
    assign CONFIG_BUSY=!FAILED && (!config_ready || (PLL_ENABLE && !TRACKING));

    IntegerPLL_DigitalCore #(.DLF_FRAC_WIDTH(2),.DLF_PROP_RAIL_GUARD(1),
        .MMD_REGISTER_CONFIG(1),
        .MMD_RATIO_WIDTH(5),
        .MMD_COUNTDOWN(1),
        .MMD_CONFIG_PIPELINE(1),
        .SYNCHRONIZE_RESETS(1),
        .BBPD_EVENT_CDC(1),
        .BBPD_CAPTURE_INDEPENDENT(1),
        .REGISTER_BBPD_DECISION(DLF_UPDATE_ON_PLLOUT==0),
        .DLF_UPDATE_ON_PLLOUT(DLF_UPDATE_ON_PLLOUT)) core(
        .PLLOUT(PLLOUT),.RESET_N(oscillator_reset_n),.BBPD(BBPD),
        .BBPD_CAPTURE_EN(track_pipe[1]),
        .DLF_En(TRACKING),.DLF_Clear(!TRACKING),.DLF_Ext_Override(1'b0),
        .DLF_IN_POL(fine_increasing),.DLF_Ext_Data({fine_seed,2'b00}),
        .DLF_KI(fine_ki),.DLF_KP(fine_kp),
        // The reference-owned coarse code can restart an oscillator that is
        // too slow or stopped; acquisition waits for the seed acknowledgement.
        .COARSEBINARY_CODE(COARSE_CODE),.MMDCLKDIV_RATIO({3'b000,local_divider}),
        .CLKDIV_RETIMED(CLKDIV_RETIMED),.DCO_CODE(core_dco_code),.DLF_CODE(DLF_CODE),
        .COARSETHERMAL_CODE(core_coarse_therm),.DCO_THERM(core_dco_therm),
        .PLLOUT_DIV(),.Medium_BINARY_CODE(),.Fine_BINARY_CODE(),
        .Medium_CAPS_CTRL(),.Fine_CAPS_CTRL());
    /* verilator lint_on PINCONNECTEMPTY */
endmodule
`default_nettype wire
