// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_HardMacroTop_EINVP_25MHzConfigured #(
    parameter MODE_CLEAR_CYCLES = 4
) (
`ifdef USE_POWER_PINS
    inout wire VPWR,
    inout wire VGND,
    inout wire VPB,
    inout wire VNB,
`endif
    input wire REF,
    input wire RESET_N,
    input wire PLL_ENABLE,
    input wire [4:0] FEEDBACK_DIVIDER,
    output wire PLLOUT,
    output wire PLLOUT_DIV,
    output wire CLKDIV_RETIMED,
    output wire [1:0] BBPD_CODE,
    output wire [7:0] DCO_CODE,
    output wire [9:0] DLF_CODE,
    output wire CONFIG_BUSY,
    output wire TRACKING,
    output wire [15:0] TARGET_MHZ,
    output wire [7:0] TARGET_DCO_CODE,
    output wire CONFIG_VALID
);

    wire dlf_en;
    wire dlf_clear;
    wire dlf_ext_override;
    wire dlf_in_pol;
    wire [9:0] dlf_ext_data;
    wire [7:0] dlf_ki;
    wire [7:0] dlf_kp;
    wire [5:0] coarse_code;
    wire [7:0] mmd_ratio;
    wire pllo_internal;
    (* keep = "true" *) wire [15:0] target_mhz_raw;

    assign PLLOUT = pllo_internal;
    assign TARGET_MHZ[7:0] = target_mhz_raw[7:0];
    assign TARGET_MHZ[15:9] = target_mhz_raw[15:9];

    /*
     * TARGET_MHZ[8] has the longest status-output route in this wrapper. The
     * explicit physical buffer keeps its decode net local while preserving the
     * generic RTL simulation path.
     */
`ifdef USE_POWER_PINS
    /* verilator lint_off PINMISSING */
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 target_mhz8_status_buf (
        .X(TARGET_MHZ[8]),
        .A(target_mhz_raw[8])
    );
    /* verilator lint_on PINMISSING */
`else
    assign TARGET_MHZ[8] = target_mhz_raw[8];
`endif

    IntegerPLL_25MHzModeController #(
        .CLEAR_CYCLES(MODE_CLEAR_CYCLES)
    ) mode_controller (
        .CLKDIV_RETIMED(CLKDIV_RETIMED),
        .RESET_N(RESET_N),
        .PLL_ENABLE(PLL_ENABLE),
        .FEEDBACK_DIVIDER(FEEDBACK_DIVIDER),
        .DLF_En(dlf_en),
        .DLF_Clear(dlf_clear),
        .DLF_Ext_Override(dlf_ext_override),
        .DLF_IN_POL(dlf_in_pol),
        .DLF_Ext_Data(dlf_ext_data),
        .DLF_KI(dlf_ki),
        .DLF_KP(dlf_kp),
        .COARSEBINARY_CODE(coarse_code),
        .MMDCLKDIV_RATIO(mmd_ratio),
        .CONFIG_BUSY(CONFIG_BUSY),
        .TRACKING(TRACKING),
        .TARGET_MHZ(target_mhz_raw),
        .TARGET_DCO_CODE(TARGET_DCO_CODE),
        .CONFIG_VALID(CONFIG_VALID)
    );

    IntegerPLL_HardMacroTop_EINVP hard_macro (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),
        .VGND(VGND),
        .VPB(VPB),
        .VNB(VNB),
`endif
        .REF(REF),
        .RESET_N(RESET_N),
        .DLF_En(dlf_en),
        .DLF_Clear(dlf_clear),
        .DLF_Ext_Override(dlf_ext_override),
        .DLF_IN_POL(dlf_in_pol),
        .DLF_Ext_Data(dlf_ext_data),
        .DLF_KI(dlf_ki),
        .DLF_KP(dlf_kp),
        .COARSEBINARY_CODE(coarse_code),
        .MMDCLKDIV_RATIO(mmd_ratio),
        .PLLOUT(pllo_internal),
        .PLLOUT_DIV(PLLOUT_DIV),
        .CLKDIV_RETIMED(CLKDIV_RETIMED),
        .BBPD_CODE(BBPD_CODE),
        .DCO_CODE(DCO_CODE),
        .DLF_CODE(DLF_CODE)
    );

endmodule

`default_nettype wire
