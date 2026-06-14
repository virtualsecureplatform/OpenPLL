// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_HardMacroTop_EINVP (
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
    input wire [7:0] DLF_KP,
    input wire [5:0] COARSEBINARY_CODE,
    input wire [7:0] MMDCLKDIV_RATIO,
    output wire PLLOUT,
    output wire PLLOUT_DIV,
    output wire CLKDIV_RETIMED,
    output wire [1:0] BBPD_CODE,
    output wire [7:0] DCO_CODE,
    output wire [9:0] DLF_CODE
);

    assign PLLOUT = REF && RESET_N;
    assign PLLOUT_DIV = DLF_En && !DLF_Clear;
    assign CLKDIV_RETIMED = REF && (MMDCLKDIV_RATIO != 8'd0);
    assign BBPD_CODE = DLF_Ext_Override ? 2'b00 : {DLF_IN_POL, DLF_En};
    assign DCO_CODE = DLF_Ext_Data[9:2] ^ {2'b00, COARSEBINARY_CODE};
    assign DLF_CODE = DLF_Ext_Data ^ {DLF_KI[3:0], DLF_KP[5:0]};

endmodule

`default_nettype wire
