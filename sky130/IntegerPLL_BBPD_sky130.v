// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_BBPD (
`ifdef USE_POWER_PINS
    inout wire VPWR,
    inout wire VGND,
    inout wire VPB,
    inout wire VNB,
`endif
    input wire REF,
    input wire CLKDIVR,
    input wire RESET_N,
    output wire [1:0] BBPD
);

`ifndef USE_POWER_PINS
    supply1 VPWR;
    supply1 VPB;
    supply0 VGND;
    supply0 VNB;
`endif

`ifdef USE_CELL_POWER_PINS
`define INTEGERPLL_SKY130_CELL_PG .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`else
`define INTEGERPLL_SKY130_CELL_PG
`endif

    wire logic1;
    wire logic0;
    wire up_q;
    wire dn_q;
    wire up_d1;
    wire up_d2;
    wire dn_d1;
    wire dn_d2;
    wire both_high;
    wire reset_b;

    sky130_fd_sc_hd__conb_1 consts (
        `INTEGERPLL_SKY130_CELL_PG
        .HI(logic1),
        .LO(logic0)
    );

    sky130_fd_sc_hd__buf_1 up_delay_0 (
        `INTEGERPLL_SKY130_CELL_PG
        .X(up_d1),
        .A(up_q)
    );

    sky130_fd_sc_hd__buf_1 up_delay_1 (
        `INTEGERPLL_SKY130_CELL_PG
        .X(up_d2),
        .A(up_d1)
    );

    sky130_fd_sc_hd__buf_1 dn_delay_0 (
        `INTEGERPLL_SKY130_CELL_PG
        .X(dn_d1),
        .A(dn_q)
    );

    sky130_fd_sc_hd__buf_1 dn_delay_1 (
        `INTEGERPLL_SKY130_CELL_PG
        .X(dn_d2),
        .A(dn_d1)
    );

    sky130_fd_sc_hd__and2_1 both_high_gate (
        `INTEGERPLL_SKY130_CELL_PG
        .X(both_high),
        .A(up_d2),
        .B(dn_d2)
    );

    sky130_fd_sc_hd__and2b_1 reset_gate (
        `INTEGERPLL_SKY130_CELL_PG
        .X(reset_b),
        .A_N(both_high),
        .B(RESET_N)
    );

    sky130_fd_sc_hd__dfrtp_1 up_ff (
        `INTEGERPLL_SKY130_CELL_PG
        .Q(up_q),
        .CLK(REF),
        .D(logic1),
        .RESET_B(reset_b)
    );

    sky130_fd_sc_hd__dfrtp_1 dn_ff (
        `INTEGERPLL_SKY130_CELL_PG
        .Q(dn_q),
        .CLK(CLKDIVR),
        .D(logic1),
        .RESET_B(reset_b)
    );

    sky130_fd_sc_hd__buf_1 up_out (
        `INTEGERPLL_SKY130_CELL_PG
        .X(BBPD[1]),
        .A(up_q)
    );

    sky130_fd_sc_hd__buf_1 dn_out (
        `INTEGERPLL_SKY130_CELL_PG
        .X(BBPD[0]),
        .A(dn_q)
    );

endmodule

`undef INTEGERPLL_SKY130_CELL_PG
`default_nettype wire
