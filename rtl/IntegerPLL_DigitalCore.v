// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_DigitalCore #(
    parameter DLF_CODE_WIDTH = 10,
    parameter DLF_FRAC_WIDTH = 8,
    parameter DLF_GAIN_WIDTH = 8,
    parameter DLF_ACQ_BOOST_SHIFT = 0,
    parameter DLF_ACQ_BOOST_AFTER = 3,
    parameter DLF_ACQ_RAIL_BOOST = 0,
    parameter DLF_ACQ_FORCE_RAIL_CODE = 0,
    parameter DLF_UPDATE_ON_PLLOUT = 0,
    parameter DLF_PROP_RAIL_GUARD = 0,
    parameter THERM_INVERT = 0,
    parameter DCO_THERM_INVERT = 1,
    parameter DCO_CONTROL_REGISTERED = 1,
    parameter DCO_COARSE_BITS = 0
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
    input wire [DLF_GAIN_WIDTH-1:0] DLF_KP,
    input wire [3:0] COARSEBINARY_CODE,
    input wire [7:0] MMDCLKDIV_RATIO,
    output wire CLKDIV_RETIMED,
    output wire PLLOUT_DIV,
    output wire [14:0] COARSETHERMAL_CODE,
    output wire [4:0] Medium_BINARY_CODE,
    output wire [4:0] Fine_BINARY_CODE,
    output wire [30:0] Medium_CAPS_CTRL,
    output wire [30:0] Fine_CAPS_CTRL,
    output wire [7:0] DCO_CODE,
    output wire [254:0] DCO_THERM,
    output wire [DLF_CODE_WIDTH-1:0] DLF_CODE
);

    localparam integer DCO_CODE_WIDTH = 8;
    localparam integer DCO_FINE_BITS = DCO_CODE_WIDTH - DCO_COARSE_BITS;

    reg clkdiv_sampled;
    reg clkdiv_sampled_d;
    reg bbpd_up_event_toggle;
    reg bbpd_dn_event_toggle;
    reg bbpd_up_event_sync;
    reg bbpd_dn_event_sync;
    reg bbpd_up_event_consumed;
    reg bbpd_dn_event_consumed;
    reg [1:0] bbpd_seen;
    reg [1:0] bbpd_decision;
    reg dlf_update_edge_q;

    wire dlf_update_edge;
    wire dlf_clk;
    wire dlf_update;
    wire bbpd_capture_active;
    wire bbpd_event_reset_n;
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
    assign bbpd_capture_active = DLF_En && !DLF_Clear;
    assign bbpd_event_reset_n = RESET_N && bbpd_capture_active;
    assign bbpd_up_event_new = bbpd_up_event_sync ^ bbpd_up_event_consumed;
    assign bbpd_dn_event_new = bbpd_dn_event_sync ^ bbpd_dn_event_consumed;
    assign bbpd_event_decision = bbpd_up_event_new ? 2'b10 :
                                 bbpd_dn_event_new ? 2'b01 :
                                 2'b00;
    assign bbpd_seen_next = (bbpd_seen != 2'b00) ? bbpd_seen :
                            bbpd_event_decision;

    IntegerPLL_MMD_Retimer #(
        .RATIO_WIDTH(8)
    ) feedback_divider (
        .DIV_IN(PLLOUT),
        .RESET_N(RESET_N),
        .CLK_DIV_RATIO(MMDCLKDIV_RATIO),
        .CLKDIV_RETIMED(CLKDIV_RETIMED)
    );

    IntegerPLL_DLF #(
        .CODE_WIDTH(DLF_CODE_WIDTH),
        .FRAC_WIDTH(DLF_FRAC_WIDTH),
        .GAIN_WIDTH(DLF_GAIN_WIDTH),
        .DCO_CODE_WIDTH(DCO_FINE_BITS),
        .ACQ_BOOST_SHIFT(DLF_ACQ_BOOST_SHIFT),
        .ACQ_BOOST_AFTER(DLF_ACQ_BOOST_AFTER),
        .ACQ_RAIL_BOOST(DLF_ACQ_RAIL_BOOST),
        .ACQ_FORCE_RAIL_CODE(DLF_ACQ_FORCE_RAIL_CODE),
        .PROP_RAIL_GUARD(DLF_PROP_RAIL_GUARD),
        .THERM_INVERT(THERM_INVERT)
    ) loop_filter (
        .CLK(dlf_clk),
        .RESET_N(RESET_N),
        .DLF_En(DLF_En),
        .DLF_Clear(DLF_Clear),
        .DLF_Ext_Override(DLF_Ext_Override),
        .DLF_Update(dlf_update),
        .DLF_IN_POL(DLF_IN_POL),
        .DLF_Ext_Data(DLF_Ext_Data),
        .DLF_KI(DLF_KI),
        .DLF_KP(DLF_KP),
        .BBPD(bbpd_decision),
        .Medium_BINARY_CODE(Medium_BINARY_CODE),
        .Fine_BINARY_CODE(Fine_BINARY_CODE),
        .Medium_CAPS_CTRL(Medium_CAPS_CTRL),
        .Fine_CAPS_CTRL(Fine_CAPS_CTRL),
        .DLF_CODE(DLF_CODE)
    );

    IntegerPLL_B2TH #(
        .BIN_WIDTH(4),
        .THERM_WIDTH(15),
        .INVERT_OUTPUT(THERM_INVERT)
    ) coarse_decoder (
        .binary_code(COARSEBINARY_CODE),
        .thermal_code(COARSETHERMAL_CODE)
    );

    assign dco_code_raw = DLF_CODE[DLF_CODE_WIDTH-1:DLF_CODE_WIDTH-8];
    assign dco_fine_mask = 8'hff >> DCO_COARSE_BITS;
    assign dco_fine_code = (dco_code_raw >> DCO_COARSE_BITS) & dco_fine_mask;
    assign dco_coarse_code =
        ({4'b0000, COARSEBINARY_CODE} << DCO_FINE_BITS) &
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

            always @(posedge dlf_clk or negedge RESET_N) begin
                if (!RESET_N) begin
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

    always @(posedge PLLOUT or negedge RESET_N) begin
        if (!RESET_N) begin
            clkdiv_sampled <= 1'b0;
            clkdiv_sampled_d <= 1'b0;
            bbpd_up_event_sync <= 1'b0;
            bbpd_dn_event_sync <= 1'b0;
            bbpd_up_event_consumed <= 1'b0;
            bbpd_dn_event_consumed <= 1'b0;
            bbpd_seen <= 2'b00;
            bbpd_decision <= 2'b00;
            dlf_update_edge_q <= 1'b0;
        end else begin
            clkdiv_sampled <= CLKDIV_RETIMED;
            clkdiv_sampled_d <= clkdiv_sampled;
            if (!bbpd_capture_active) begin
                bbpd_up_event_sync <= 1'b0;
                bbpd_dn_event_sync <= 1'b0;
                bbpd_up_event_consumed <= 1'b0;
                bbpd_dn_event_consumed <= 1'b0;
                bbpd_seen <= 2'b00;
                bbpd_decision <= 2'b00;
                dlf_update_edge_q <= 1'b0;
            end else begin
                dlf_update_edge_q <= dlf_update_edge;
                bbpd_up_event_sync <= bbpd_up_event_toggle;
                bbpd_dn_event_sync <= bbpd_dn_event_toggle;
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
        else if (!BBPD[0] && (bbpd_up_event_toggle == bbpd_up_event_consumed))
            bbpd_up_event_toggle <= ~bbpd_up_event_toggle;
    end

    always @(posedge BBPD[0] or negedge bbpd_event_reset_n) begin
        if (!bbpd_event_reset_n)
            bbpd_dn_event_toggle <= 1'b0;
        else if (!BBPD[1] && (bbpd_dn_event_toggle == bbpd_dn_event_consumed))
            bbpd_dn_event_toggle <= ~bbpd_dn_event_toggle;
    end

    IntegerPLL_Divider test_divider (
        .CLK(PLLOUT),
        .RESET_N(RESET_N),
        .PLLOUT_DIV(PLLOUT_DIV)
    );

endmodule

`default_nettype wire
