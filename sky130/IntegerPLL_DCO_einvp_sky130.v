// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_DCO_EINVP (
`ifdef USE_POWER_PINS
    inout wire VPWR,
    inout wire VGND,
    inout wire VPB,
    inout wire VNB,
`endif
    input wire RESET_N,
    input wire [254:0] DCO_THERM,
    output wire PLLOUT
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

    wire [16:0] ring;
    wire [254:0] load_dummy;

    sky130_fd_sc_hd__nand2_1 osc_gate (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(ring[0]),
        .A(ring[16]),
        .B(RESET_N)
    );

    genvar i;
    generate
        for (i = 1; i < 17; i = i + 1) begin : gen_ring_inv
            sky130_fd_sc_hd__inv_1 ring_inv (
                `INTEGERPLL_SKY130_CELL_PG
                .Y(ring[i]),
                .A(ring[i-1])
            );
        end
    endgenerate

    sky130_fd_sc_hd__buf_1 out_buf (
        `INTEGERPLL_SKY130_CELL_PG
        .X(PLLOUT),
        .A(ring[16])
    );

    genvar f;
    generate
        for (f = 0; f < 255; f = f + 1) begin : gen_dco_load
            sky130_fd_sc_hd__einvp_1 tune_load (
                `INTEGERPLL_SKY130_CELL_PG
                .Z(load_dummy[f]),
                .A(ring[f % 17]),
                .TE(DCO_THERM[f])
            );
        end
    endgenerate

endmodule

`undef INTEGERPLL_SKY130_CELL_PG
`default_nettype wire
