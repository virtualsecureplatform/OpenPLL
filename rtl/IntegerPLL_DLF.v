// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_DLF #(
    parameter CODE_WIDTH = 10,
    parameter FRAC_WIDTH = 8,
    parameter GAIN_WIDTH = 8,
    parameter DCO_CODE_WIDTH = 8,
    parameter ACQ_BOOST_SHIFT = 0,
    parameter ACQ_BOOST_AFTER = 3,
    parameter ACQ_RAIL_BOOST = 0,
    parameter ACQ_FORCE_RAIL_CODE = 0,
    parameter PROP_RAIL_GUARD = 0,
    parameter THERM_INVERT = 0
) (
    input wire CLK,
    input wire RESET_N,
    input wire DLF_En,
    input wire DLF_Clear,
    input wire DLF_Ext_Override,
    input wire DLF_Update,
    input wire DLF_IN_POL,
    input wire [CODE_WIDTH-1:0] DLF_Ext_Data,
    input wire [GAIN_WIDTH-1:0] DLF_KI,
    input wire [GAIN_WIDTH-1:0] DLF_KP,
    input wire [1:0] BBPD,
    output wire [4:0] Medium_BINARY_CODE,
    output wire [4:0] Fine_BINARY_CODE,
    output wire [30:0] Medium_CAPS_CTRL,
    output wire [30:0] Fine_CAPS_CTRL,
    output wire [CODE_WIDTH-1:0] DLF_CODE
);

    localparam ACC_WIDTH = CODE_WIDTH + FRAC_WIDTH + 1;

    localparam signed [ACC_WIDTH-1:0] ACC_ZERO =
        {ACC_WIDTH{1'b0}};
    localparam signed [ACC_WIDTH-1:0] ACC_MAX =
        {1'b0, {CODE_WIDTH{1'b1}}, {FRAC_WIDTH{1'b0}}};
    localparam signed [ACC_WIDTH:0] ACC_ZERO_WIDE =
        {(ACC_WIDTH + 1){1'b0}};
    localparam signed [ACC_WIDTH:0] ACC_MAX_WIDE =
        {1'b0, ACC_MAX};
    localparam integer KP_PAD_WIDTH = ACC_WIDTH - GAIN_WIDTH - FRAC_WIDTH;
    localparam integer DCO_CODE_SHIFT = CODE_WIDTH - DCO_CODE_WIDTH;
    localparam integer ACQ_COUNT_WIDTH = 4;
    localparam [ACQ_COUNT_WIDTH-1:0] ACQ_BOOST_AFTER_COUNT = ACQ_BOOST_AFTER;
    localparam [CODE_WIDTH-1:0] DCO_CODE_HIGH_RAIL =
        {{DCO_CODE_WIDTH{1'b1}}, {DCO_CODE_SHIFT{1'b0}}};
    localparam [CODE_WIDTH-1:0] DCO_CODE_LOW_VISIBLE_NEXT =
        (1 << DCO_CODE_SHIFT);
    localparam [CODE_WIDTH-1:0] ACQ_FORCE_LOW_LIMIT =
        (ACQ_FORCE_RAIL_CODE << DCO_CODE_SHIFT);
    localparam [CODE_WIDTH-1:0] ACQ_FORCE_HIGH_LIMIT =
        (((1 << DCO_CODE_WIDTH) - 1 - ACQ_FORCE_RAIL_CODE) << DCO_CODE_SHIFT);
    localparam signed [ACC_WIDTH:0] ACC_DCO_CODE_LOW_VISIBLE_NEXT_WIDE =
        $signed({2'b00, DCO_CODE_LOW_VISIBLE_NEXT, {FRAC_WIDTH{1'b0}}});
    localparam signed [ACC_WIDTH:0] ACC_DCO_CODE_HIGH_RAIL_WIDE =
        $signed({2'b00, DCO_CODE_HIGH_RAIL, {FRAC_WIDTH{1'b0}}});

    reg signed [ACC_WIDTH-1:0] integ_acc;
    reg acq_last_inc;
    reg acq_last_dec;
    reg [ACQ_COUNT_WIDTH-1:0] acq_same_dir_count;

    wire bbpd_inc_raw;
    wire bbpd_dec_raw;
    wire bbpd_inc;
    wire bbpd_dec;
    wire bbpd_inc_eff;
    wire bbpd_dec_eff;
    wire acq_force_inc;
    wire acq_force_dec;
    wire loop_active;
    wire update_active;

    wire signed [ACC_WIDTH-1:0] ki_mag_base;
    wire signed [ACC_WIDTH-1:0] ki_mag_boosted;
    wire signed [ACC_WIDTH-1:0] ki_mag;
    wire signed [ACC_WIDTH-1:0] kp_mag;
    wire signed [ACC_WIDTH-1:0] ki_delta;
    wire signed [ACC_WIDTH-1:0] kp_delta;
    wire signed [ACC_WIDTH:0] integ_acc_wide;
    wire signed [ACC_WIDTH:0] kp_mag_wide;
    wire signed [ACC_WIDTH:0] integ_next_wide;
    wire signed [ACC_WIDTH:0] prop_wide;
    wire signed [ACC_WIDTH:0] prop_inc_wide;
    wire signed [ACC_WIDTH:0] prop_dec_wide;
    wire signed [ACC_WIDTH-1:0] loop_acc;
    /* verilator lint_off UNUSEDSIGNAL */
    wire signed [ACC_WIDTH-1:0] prop_acc;
    /* verilator lint_on UNUSEDSIGNAL */
    wire [CODE_WIDTH-1:0] integ_code;
    wire [CODE_WIDTH-1:0] loop_code;
    wire signed [ACC_WIDTH-1:0] ext_acc;
    wire acq_dir_seen;
    wire acq_same_dir;
    wire acq_rail_boost_region;
    wire acq_boost_active;
    wire prop_low_rail_guard;
    wire prop_high_rail_guard;

    function signed [ACC_WIDTH-1:0] sat_acc;
        input signed [ACC_WIDTH:0] value;
        begin
            if (value <= ACC_ZERO_WIDE)
                sat_acc = ACC_ZERO;
            else if (value >= ACC_MAX_WIDE)
                sat_acc = ACC_MAX;
            else
                sat_acc = value[ACC_WIDTH-1:0];
        end
    endfunction

    assign bbpd_inc_raw = (BBPD == 2'b10);
    assign bbpd_dec_raw = (BBPD == 2'b01);
    assign bbpd_inc = DLF_IN_POL ? bbpd_inc_raw : bbpd_dec_raw;
    assign bbpd_dec = DLF_IN_POL ? bbpd_dec_raw : bbpd_inc_raw;
    assign loop_active = DLF_En && !DLF_Ext_Override;
    assign update_active = loop_active && DLF_Update;
    assign integ_code = integ_acc[FRAC_WIDTH+CODE_WIDTH-1:FRAC_WIDTH];
    assign kp_mag = $signed({{KP_PAD_WIDTH{1'b0}}, DLF_KP, {FRAC_WIDTH{1'b0}}});
    assign integ_acc_wide = {integ_acc[ACC_WIDTH-1], integ_acc};
    assign kp_mag_wide = {kp_mag[ACC_WIDTH-1], kp_mag};
    assign prop_inc_wide = integ_acc_wide + kp_mag_wide;
    assign prop_dec_wide = integ_acc_wide - kp_mag_wide;
    assign prop_low_rail_guard =
        (PROP_RAIL_GUARD != 0) &&
        (prop_dec_wide < ACC_DCO_CODE_LOW_VISIBLE_NEXT_WIDE);
    assign prop_high_rail_guard =
        (PROP_RAIL_GUARD != 0) &&
        (prop_inc_wide >= ACC_DCO_CODE_HIGH_RAIL_WIDE);
    assign acq_force_inc =
        update_active &&
        (ACQ_FORCE_RAIL_CODE > 0) &&
        (integ_code < ACQ_FORCE_LOW_LIMIT);
    assign acq_force_dec =
        update_active &&
        (ACQ_FORCE_RAIL_CODE > 0) &&
        (integ_code > ACQ_FORCE_HIGH_LIMIT);
    assign bbpd_inc_eff =
        acq_force_inc ||
        (!acq_force_dec &&
         ((bbpd_inc && !prop_high_rail_guard && (integ_code < DCO_CODE_HIGH_RAIL)) ||
          (((integ_code == {CODE_WIDTH{1'b0}}) || prop_low_rail_guard) && bbpd_dec)));
    assign bbpd_dec_eff =
        acq_force_dec ||
        (!acq_force_inc &&
         ((bbpd_dec && !prop_low_rail_guard && (integ_code != {CODE_WIDTH{1'b0}})) ||
          (((integ_code >= DCO_CODE_HIGH_RAIL) || prop_high_rail_guard) && bbpd_inc)));

    assign ki_mag_base = $signed({{(ACC_WIDTH-GAIN_WIDTH){1'b0}}, DLF_KI});
    assign ki_mag_boosted = $signed(ki_mag_base << ACQ_BOOST_SHIFT);
    assign acq_dir_seen = bbpd_inc_eff || bbpd_dec_eff;
    assign acq_same_dir = (bbpd_inc_eff && acq_last_inc) ||
                          (bbpd_dec_eff && acq_last_dec);
    assign acq_rail_boost_region =
        (ACQ_RAIL_BOOST != 0) &&
        ((integ_code == {CODE_WIDTH{1'b0}}) ||
         (integ_code >= DCO_CODE_HIGH_RAIL) ||
         acq_force_inc ||
         acq_force_dec ||
         prop_low_rail_guard ||
         prop_high_rail_guard);
    assign acq_boost_active =
        (ACQ_BOOST_SHIFT > 0) &&
        update_active &&
        acq_dir_seen &&
        (acq_rail_boost_region ||
         (acq_same_dir && (acq_same_dir_count >= ACQ_BOOST_AFTER_COUNT)));
    assign ki_mag = acq_boost_active ? ki_mag_boosted : ki_mag_base;

    assign ki_delta = (!update_active) ? {ACC_WIDTH{1'b0}} :
                      bbpd_inc_eff ? ki_mag :
                      bbpd_dec_eff ? -ki_mag :
                      {ACC_WIDTH{1'b0}};

    assign kp_delta = (!loop_active) ? {ACC_WIDTH{1'b0}} :
                      bbpd_inc_eff ? kp_mag :
                      bbpd_dec_eff ? -kp_mag :
                      {ACC_WIDTH{1'b0}};

    assign integ_next_wide = integ_acc_wide +
                             {ki_delta[ACC_WIDTH-1], ki_delta};
    assign loop_acc = sat_acc(integ_next_wide);

    assign prop_wide = integ_acc_wide +
                       {kp_delta[ACC_WIDTH-1], kp_delta};
    assign prop_acc = sat_acc(prop_wide);

    assign loop_code = prop_acc[FRAC_WIDTH+CODE_WIDTH-1:FRAC_WIDTH];
    assign DLF_CODE = (DLF_Ext_Override || DLF_Clear) ? DLF_Ext_Data : loop_code;

    assign Medium_BINARY_CODE = DLF_CODE[9:5];
    assign Fine_BINARY_CODE = DLF_CODE[4:0];

    assign ext_acc = $signed({1'b0, DLF_Ext_Data, {FRAC_WIDTH{1'b0}}});

    always @(posedge CLK or negedge RESET_N) begin
        if (!RESET_N)
            integ_acc <= ACC_ZERO;
        else if (DLF_Clear)
            integ_acc <= ext_acc;
        else if (update_active)
            integ_acc <= loop_acc;
    end

    always @(posedge CLK or negedge RESET_N) begin
        if (!RESET_N) begin
            acq_last_inc <= 1'b0;
            acq_last_dec <= 1'b0;
            acq_same_dir_count <= {ACQ_COUNT_WIDTH{1'b0}};
        end else if (DLF_Clear || !loop_active) begin
            acq_last_inc <= 1'b0;
            acq_last_dec <= 1'b0;
            acq_same_dir_count <= {ACQ_COUNT_WIDTH{1'b0}};
        end else if (DLF_Update) begin
            if (!acq_dir_seen) begin
                acq_last_inc <= 1'b0;
                acq_last_dec <= 1'b0;
                acq_same_dir_count <= {ACQ_COUNT_WIDTH{1'b0}};
            end else begin
                acq_last_inc <= bbpd_inc_eff;
                acq_last_dec <= bbpd_dec_eff;
                if (acq_same_dir) begin
                    if (acq_same_dir_count != {ACQ_COUNT_WIDTH{1'b1}})
                        acq_same_dir_count <= acq_same_dir_count + 1'b1;
                end else begin
                    acq_same_dir_count <= {{(ACQ_COUNT_WIDTH-1){1'b0}}, 1'b1};
                end
            end
        end
    end

    IntegerPLL_B2TH #(
        .BIN_WIDTH(5),
        .THERM_WIDTH(31),
        .INVERT_OUTPUT(THERM_INVERT)
    ) medium_decoder (
        .binary_code(Medium_BINARY_CODE),
        .thermal_code(Medium_CAPS_CTRL)
    );

    IntegerPLL_B2TH #(
        .BIN_WIDTH(5),
        .THERM_WIDTH(31),
        .INVERT_OUTPUT(THERM_INVERT)
    ) fine_decoder (
        .binary_code(Fine_BINARY_CODE),
        .thermal_code(Fine_CAPS_CTRL)
    );

endmodule

`default_nettype wire
