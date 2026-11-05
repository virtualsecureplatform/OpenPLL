// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_DigitalCore #(
    parameter DLF_CODE_WIDTH = 10,
    parameter DLF_FRAC_WIDTH = 8,
    parameter DLF_GAIN_WIDTH = 8,
    parameter DLF_KP_WIDTH = 5,
    parameter DLF_ACQ_BOOST_SHIFT = 0,
    parameter DLF_ACQ_BOOST_AFTER = 3,
    parameter DLF_ACQ_RAIL_BOOST = 0,
    parameter DLF_ACQ_FORCE_RAIL_CODE = 0,
    parameter DLF_UPDATE_ON_PLLOUT = 0,
    parameter DLF_PROP_RAIL_GUARD = 0,
    parameter THERM_INVERT = 0,
    parameter DCO_THERM_INVERT = 1,
    parameter DCO_CONTROL_REGISTERED = 1,
    parameter DCO_COARSE_BITS = 0,
    parameter MMD_REGISTER_CONFIG = 0,
    parameter REGISTER_BBPD_DECISION = 0,
    parameter MMD_RATIO_WIDTH = 8,
    parameter MMD_COUNTDOWN = 0,
    // Release the external reset separately on each internal clock.
    parameter SYNCHRONIZE_RESETS = 0,
    // Pulse-clocked toggles cross through two registers without a return
    // acknowledgement. Allow one qualified event per feedback interval,
    // separated by at least three PLLOUT periods.
    parameter BBPD_EVENT_CDC = 0,
    // Independently clocked DLF enable must not drive fast event storage.
    parameter BBPD_CAPTURE_INDEPENDENT = 0
) (
    input wire PLLOUT,
    input wire RESET_N,
    input wire [1:0] BBPD,
    input wire DLF_En,
    input wire DLF_Clear,
    input wire DLF_Ext_Override,
    input wire DLF_IN_POL,
    input wire [DLF_CODE_WIDTH-1:0] DLF_Ext_Data,
    input wire [DLF_GAIN_WIDTH-1:0] DLF_KI,
    input wire [DLF_KP_WIDTH-1:0] DLF_KP,
    input wire [5:0] COARSEBINARY_CODE,
    input wire [7:0] MMDCLKDIV_RATIO,
    output wire CLKDIV_RETIMED,
    output wire PLLOUT_DIV,
    output wire [46:0] COARSETHERMAL_CODE,
    output wire [4:0] Medium_BINARY_CODE,
    output wire [4:0] Fine_BINARY_CODE,
    output wire [30:0] Medium_CAPS_CTRL,
    output wire [30:0] Fine_CAPS_CTRL,
    output wire [7:0] DCO_CODE,
    output wire [254:0] DCO_THERM,
    output wire [DLF_CODE_WIDTH-1:0] DLF_CODE,
    input wire BBPD_CAPTURE_EN
);

    localparam integer DCO_CODE_WIDTH = 8;
    localparam integer DCO_FINE_BITS = DCO_CODE_WIDTH - DCO_COARSE_BITS;

    reg clkdiv_sampled;
    reg clkdiv_sampled_d;
    reg bbpd_up_event_toggle;
    reg bbpd_dn_event_toggle;
    wire bbpd_up_event_sync;
    wire bbpd_dn_event_sync;
    reg bbpd_up_event_consumed;
    reg bbpd_dn_event_consumed;
    reg [1:0] bbpd_seen;
    reg [1:0] bbpd_decision;
    wire [1:0] loop_decision;
    reg dlf_update_edge_q;

    wire dlf_update_edge;
    wire dlf_clk;
    wire fast_reset_n, dlf_reset_n;
    wire dlf_update;
    wire bbpd_capture_active;
    wire bbpd_event_reset_n;
    wire bbpd_receive_ready;
    wire bbpd_up_event_new;
    wire bbpd_dn_event_new;
    wire [1:0] bbpd_event_decision;
    wire [1:0] bbpd_seen_next;
    wire [7:0] dco_code_raw;
    wire [7:0] dco_fine_mask;
    wire [7:0] dco_fine_code;
    wire [7:0] dco_coarse_code;
    wire [7:0] dco_code_effective;
    wire [254:0] dco_therm_raw;
    reg [7:0] dco_code_reg;
    reg [254:0] dco_therm_reg;

    assign dlf_update_edge = clkdiv_sampled & !clkdiv_sampled_d;
    assign dlf_clk = (DLF_UPDATE_ON_PLLOUT != 0) ? PLLOUT : CLKDIV_RETIMED;
    assign dlf_update = (DLF_UPDATE_ON_PLLOUT != 0) ? dlf_update_edge_q : 1'b1;
    assign bbpd_capture_active = (BBPD_CAPTURE_INDEPENDENT != 0) ?
                                 BBPD_CAPTURE_EN : (DLF_En && !DLF_Clear);
    assign bbpd_event_reset_n = fast_reset_n && bbpd_capture_active;
    assign bbpd_up_event_new = bbpd_up_event_sync ^ bbpd_up_event_consumed;
    assign bbpd_dn_event_new = bbpd_dn_event_sync ^ bbpd_dn_event_consumed;
    assign bbpd_event_decision = bbpd_up_event_new ? 2'b10 :
                                 bbpd_dn_event_new ? 2'b01 :
                                 2'b00;
    assign bbpd_seen_next = (bbpd_seen != 2'b00) ? bbpd_seen :
                            bbpd_event_decision;
    generate
        if (BBPD_EVENT_CDC != 0) begin : gen_event_cdc
            (* ASYNC_REG="TRUE" *) reg [1:0] up_pipe, dn_pipe;
            reg [1:0] capture_pipe;
            always @(posedge PLLOUT or negedge fast_reset_n) begin
                if(!fast_reset_n) begin up_pipe<=0;dn_pipe<=0;end
                else begin
                    up_pipe<={up_pipe[0],bbpd_up_event_toggle};
                    dn_pipe<={dn_pipe[0],bbpd_dn_event_toggle};
                end
            end
            // Keep the receive stages directly connected for resolution
            // time. A separate guard flushes stale samples before re-arming,
            // even after withdrawal between oscillator edges.
            always @(posedge PLLOUT or negedge bbpd_event_reset_n)
                if(!bbpd_event_reset_n) capture_pipe<=0;
                else capture_pipe<={capture_pipe[0],1'b1};
            assign bbpd_up_event_sync=up_pipe[1];
            assign bbpd_dn_event_sync=dn_pipe[1];
            assign bbpd_receive_ready=capture_pipe[1];
        end else begin : gen_legacy_event_sync
            reg up_sync, dn_sync;
            always @(posedge PLLOUT or negedge fast_reset_n) begin
                if(!fast_reset_n) begin up_sync<=0;dn_sync<=0;end
                else if(!bbpd_capture_active) begin up_sync<=0;dn_sync<=0;end
                else begin
                    up_sync<=bbpd_up_event_toggle;
                    dn_sync<=bbpd_dn_event_toggle;
                end
            end
            assign bbpd_up_event_sync=up_sync;
            assign bbpd_dn_event_sync=dn_sync;
            assign bbpd_receive_ready=1'b1;
        end
        if (SYNCHRONIZE_RESETS != 0) begin : gen_local_resets
            (* ASYNC_REG="TRUE" *) reg [1:0] fast_pipe, fine_pipe;
            always @(posedge PLLOUT or negedge RESET_N)
                if (!RESET_N) fast_pipe<=0;
                else fast_pipe<={fast_pipe[0],1'b1};
            always @(posedge dlf_clk or negedge RESET_N)
                if (!RESET_N) fine_pipe<=0;
                else fine_pipe<={fine_pipe[0],1'b1};
            assign fast_reset_n=fast_pipe[1];
            assign dlf_reset_n=fine_pipe[1];
        end else begin : gen_direct_reset
            assign fast_reset_n=RESET_N;
            assign dlf_reset_n=RESET_N;
        end
        if (REGISTER_BBPD_DECISION != 0) begin : gen_registered_decision
            reg [1:0] decision_q;
            always @(posedge dlf_clk or negedge dlf_reset_n)
                if (!dlf_reset_n) decision_q<=2'b00;
                else if (!DLF_En || DLF_Clear) decision_q<=2'b00;
                else decision_q<=bbpd_decision;
            assign loop_decision=decision_q;
        end else begin : gen_direct_decision
            assign loop_decision=bbpd_decision;
        end
    endgenerate

    IntegerPLL_MMD_Retimer #(
        .RATIO_WIDTH(MMD_RATIO_WIDTH),
        .REGISTER_CONFIG(MMD_REGISTER_CONFIG),
        .COUNTDOWN(MMD_COUNTDOWN)
    ) feedback_divider (
        .DIV_IN(PLLOUT),
        .RESET_N(fast_reset_n),
        .CLK_DIV_RATIO(MMDCLKDIV_RATIO[MMD_RATIO_WIDTH-1:0]),
        .CLKDIV_RETIMED(CLKDIV_RETIMED)
    );

    IntegerPLL_DLF #(
        .CODE_WIDTH(DLF_CODE_WIDTH),
        .FRAC_WIDTH(DLF_FRAC_WIDTH),
        .GAIN_WIDTH(DLF_GAIN_WIDTH),
        .KP_WIDTH(DLF_KP_WIDTH),
        .DCO_CODE_WIDTH(DCO_FINE_BITS),
        .ACQ_BOOST_SHIFT(DLF_ACQ_BOOST_SHIFT),
        .ACQ_BOOST_AFTER(DLF_ACQ_BOOST_AFTER),
        .ACQ_RAIL_BOOST(DLF_ACQ_RAIL_BOOST),
        .ACQ_FORCE_RAIL_CODE(DLF_ACQ_FORCE_RAIL_CODE),
        .PROP_RAIL_GUARD(DLF_PROP_RAIL_GUARD),
        .THERM_INVERT(THERM_INVERT)
    ) loop_filter (
        .CLK(dlf_clk),
        .RESET_N(dlf_reset_n),
        .DLF_En(DLF_En),
        .DLF_Clear(DLF_Clear),
        .DLF_Ext_Override(DLF_Ext_Override),
        .DLF_Update(dlf_update),
        .DLF_IN_POL(DLF_IN_POL),
        .DLF_Ext_Data(DLF_Ext_Data),
        .DLF_KI(DLF_KI),
        .DLF_KP(DLF_KP),
        .BBPD(loop_decision),
        .Medium_BINARY_CODE(Medium_BINARY_CODE),
        .Fine_BINARY_CODE(Fine_BINARY_CODE),
        .Medium_CAPS_CTRL(Medium_CAPS_CTRL),
        .Fine_CAPS_CTRL(Fine_CAPS_CTRL),
        .DLF_CODE(DLF_CODE)
    );

    IntegerPLL_B2TH #(
        .BIN_WIDTH(6),
        .THERM_WIDTH(47),
        .INVERT_OUTPUT(THERM_INVERT)
    ) coarse_decoder (
        .binary_code(COARSEBINARY_CODE),
        .thermal_code(COARSETHERMAL_CODE)
    );

    assign dco_code_raw = DLF_CODE[DLF_CODE_WIDTH-1:DLF_CODE_WIDTH-8];
    assign dco_fine_mask = 8'hff >> DCO_COARSE_BITS;
    assign dco_fine_code = (dco_code_raw >> DCO_COARSE_BITS) & dco_fine_mask;
    assign dco_coarse_code =
        ({2'b00, COARSEBINARY_CODE} << DCO_FINE_BITS) &
        ~dco_fine_mask;
    assign dco_code_effective = dco_coarse_code | dco_fine_code;

    IntegerPLL_B2TH #(
        .BIN_WIDTH(8),
        .THERM_WIDTH(255),
        .INVERT_OUTPUT(DCO_THERM_INVERT)
    ) dco_decoder (
        .binary_code(dco_code_effective),
        .thermal_code(dco_therm_raw)
    );

    generate
        if (DCO_CONTROL_REGISTERED != 0) begin : gen_registered_dco_control
            assign DCO_CODE = dco_code_reg;
            assign DCO_THERM = dco_therm_reg;

            always @(posedge dlf_clk or negedge dlf_reset_n) begin
                if (!dlf_reset_n) begin
                    dco_code_reg <= 8'h00;
                    dco_therm_reg <= (DCO_THERM_INVERT != 0) ?
                        {255{1'b1}} : {255{1'b0}};
                end else begin
                    dco_code_reg <= dco_code_effective;
                    dco_therm_reg <= dco_therm_raw;
                end
            end
        end else begin : gen_comb_dco_control
            assign DCO_CODE = dco_code_effective;
            assign DCO_THERM = dco_therm_raw;
        end
    endgenerate

    always @(posedge PLLOUT or negedge fast_reset_n) begin
        if (!fast_reset_n) begin
            clkdiv_sampled <= 1'b0;
            clkdiv_sampled_d <= 1'b0;
            bbpd_up_event_consumed <= 1'b0;
            bbpd_dn_event_consumed <= 1'b0;
            bbpd_seen <= 2'b00;
            bbpd_decision <= 2'b00;
            dlf_update_edge_q <= 1'b0;
        end else begin
            clkdiv_sampled <= CLKDIV_RETIMED;
            clkdiv_sampled_d <= clkdiv_sampled;
            if (!bbpd_capture_active || !bbpd_receive_ready) begin
                bbpd_up_event_consumed <= 1'b0;
                bbpd_dn_event_consumed <= 1'b0;
                bbpd_seen <= 2'b00;
                bbpd_decision <= 2'b00;
                dlf_update_edge_q <= 1'b0;
            end else begin
                dlf_update_edge_q <= dlf_update_edge;
                if (bbpd_seen == 2'b00) begin
                    if (bbpd_up_event_new)
                        bbpd_up_event_consumed <= bbpd_up_event_sync;
                    if (bbpd_dn_event_new)
                        bbpd_dn_event_consumed <= bbpd_dn_event_sync;
                end
                if (dlf_update_edge) begin
                    bbpd_decision <= bbpd_seen_next;
                    bbpd_seen <= 2'b00;
                end else begin
                    bbpd_seen <= bbpd_seen_next;
                end
            end
        end
    end

    always @(posedge BBPD[1] or negedge bbpd_event_reset_n) begin
        if (!bbpd_event_reset_n)
            bbpd_up_event_toggle <= 1'b0;
        else if (!BBPD[0] && (BBPD_EVENT_CDC != 0 || bbpd_up_event_toggle == bbpd_up_event_consumed))
            bbpd_up_event_toggle <= ~bbpd_up_event_toggle;
    end

    always @(posedge BBPD[0] or negedge bbpd_event_reset_n) begin
        if (!bbpd_event_reset_n)
            bbpd_dn_event_toggle <= 1'b0;
        else if (!BBPD[1] && (BBPD_EVENT_CDC != 0 || bbpd_dn_event_toggle == bbpd_dn_event_consumed))
            bbpd_dn_event_toggle <= ~bbpd_dn_event_toggle;
    end

    IntegerPLL_Divider test_divider (
        .CLK(PLLOUT),
        .RESET_N(fast_reset_n),
        .PLLOUT_DIV(PLLOUT_DIV)
    );

endmodule

`default_nettype wire
