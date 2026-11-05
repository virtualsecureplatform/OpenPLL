// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_HardMacroTop_EINVP_DUALMACRO_OSC8_REMAP_LOAD24_GUARD (
`ifdef USE_POWER_PINS
    inout wire VPWR,
    inout wire VGND,
    inout wire VPB,
    inout wire VNB,
`endif
    input wire REF,
    input wire RESET_N,
    input wire DLF_En,
    input wire DLF_Clear,
    input wire DLF_Ext_Override,
    input wire DLF_IN_POL,
    input wire [9:0] DLF_Ext_Data,
    input wire [7:0] DLF_KI,
    input wire [4:0] DLF_KP,
    input wire [5:0] COARSEBINARY_CODE,
    input wire [7:0] MMDCLKDIV_RATIO,
    output wire PLLOUT,
    output wire PLLOUT_DIV,
    output wire CLKDIV_RETIMED,
    output wire [1:0] BBPD_CODE,
    output wire [7:0] DCO_CODE,
    output wire [9:0] DLF_CODE
);

    wire [46:0] coarse_ctrl;
    wire [4:0] medium_binary;
    wire [4:0] fine_binary;
    wire [30:0] medium_ctrl;
    wire [30:0] fine_ctrl;
    wire [254:0] dco_therm;
    wire bbpd_reset_n;

    // Uniform gate area on top-level controls and the DCO control branches.
    // The outputs are intentionally unused; the complete assembly must be
    // characterized before release.
    wire [347:0] antenna_guard_input = {
        dco_therm, coarse_ctrl, BBPD_CODE, CLKDIV_RETIMED,
        DLF_Ext_Data, DLF_KI, DLF_KP, COARSEBINARY_CODE,
        MMDCLKDIV_RATIO, REF, RESET_N, DLF_En, DLF_Clear,
        DLF_Ext_Override, DLF_IN_POL
    };
    wire [347:0] antenna_guard_sink;
    genvar guard_bit;
    generate
        for (guard_bit = 0; guard_bit < 348; guard_bit = guard_bit + 1) begin : gen_antenna_guard
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_16 guard_load (
                .A(antenna_guard_input[guard_bit]),
                .X(antenna_guard_sink[guard_bit])
            );
        end
    endgenerate

    wire [254:0] dco_therm_extra_guard_sink;
    genvar dco_guard_bit;
    generate
        for (dco_guard_bit = 0; dco_guard_bit < 255; dco_guard_bit = dco_guard_bit + 1) begin : gen_dco_extra_guard
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_16 guard_load (
                .A(dco_therm[dco_guard_bit]),
                .X(dco_therm_extra_guard_sink[dco_guard_bit])
            );
        end
    endgenerate

    wire dlf_kp4_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_16 dlf_kp4_extra_guard (
        .A(DLF_KP[4]), .X(dlf_kp4_extra_guard_sink)
    );

    wire dlf_ext_data3_buffered;
    wire dlf_ki3_buffered;
    wire [7:0] mmd_ratio_to_core;
    wire [9:0] dlf_ext_data_to_core = {
        DLF_Ext_Data[9:4], dlf_ext_data3_buffered, DLF_Ext_Data[2:0]
    };
    wire [7:0] dlf_ki_to_core = {
        DLF_KI[7:4], dlf_ki3_buffered, DLF_KI[2:0]
    };
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 dlf_ext_data3_driver (
        .A(DLF_Ext_Data[3]), .X(dlf_ext_data3_buffered)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 dlf_ki3_driver (
        .A(DLF_KI[3]), .X(dlf_ki3_buffered)
    );
    wire [7:0] mmd_ratio_branch_guard_sink;
    genvar ratio_bit;
    generate
        for (ratio_bit = 0; ratio_bit < 8; ratio_bit = ratio_bit + 1) begin : gen_mmd_ratio_buffer
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 driver (
                .A(MMDCLKDIV_RATIO[ratio_bit]), .X(mmd_ratio_to_core[ratio_bit])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 branch_guard (
                .A(mmd_ratio_to_core[ratio_bit]), .X(mmd_ratio_branch_guard_sink[ratio_bit])
            );
        end
    endgenerate
    wire [4:0] additional_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 dlf_ext_data2_guard (
        .A(DLF_Ext_Data[2]), .X(additional_guard_sink[0])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 dco_therm95_guard (
        .A(dco_therm[95]), .X(additional_guard_sink[1])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 dco_therm252_guard (
        .A(dco_therm[252]), .X(additional_guard_sink[2])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 dlf_ext_data3_branch_guard (
        .A(dlf_ext_data3_buffered), .X(additional_guard_sink[3])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 dlf_ki3_branch_guard (
        .A(dlf_ki3_buffered), .X(additional_guard_sink[4])
    );

    assign bbpd_reset_n = RESET_N && DLF_En && !DLF_Clear;

    IntegerPLL_BBPD phase_detector (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),
        .VGND(VGND),
        .VPB(VPB),
        .VNB(VNB),
`endif
        .REF(REF),
        .CLKDIVR(CLKDIV_RETIMED),
        .RESET_N(bbpd_reset_n),
        .BBPD(BBPD_CODE)
    );

    IntegerPLL_DigitalCore digital_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),
        .VGND(VGND),
`endif
        .PLLOUT(PLLOUT),
        .RESET_N(RESET_N),
        .BBPD(BBPD_CODE),
        .DLF_En(DLF_En),
        .DLF_Clear(DLF_Clear),
        .DLF_Ext_Override(DLF_Ext_Override),
        .DLF_IN_POL(DLF_IN_POL),
        .DLF_Ext_Data(dlf_ext_data_to_core),
        .DLF_KI(dlf_ki_to_core),
        .DLF_KP(DLF_KP),
        .COARSEBINARY_CODE(COARSEBINARY_CODE),
        .MMDCLKDIV_RATIO(mmd_ratio_to_core),
        .CLKDIV_RETIMED(CLKDIV_RETIMED),
        .PLLOUT_DIV(PLLOUT_DIV),
        .COARSETHERMAL_CODE(coarse_ctrl),
        .Medium_BINARY_CODE(medium_binary),
        .Fine_BINARY_CODE(fine_binary),
        .Medium_CAPS_CTRL(medium_ctrl),
        .Fine_CAPS_CTRL(fine_ctrl),
        .DCO_CODE(DCO_CODE),
        .DCO_THERM(dco_therm),
        .DLF_CODE(DLF_CODE)
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_LOAD24_DBUF_GUARD oscillator (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),
        .VGND(VGND),
        .VPB(VPB),
        .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE(coarse_ctrl),
        .DCO_THERM(dco_therm),
        .PLLOUT(PLLOUT)
    );

endmodule

`default_nettype wire
