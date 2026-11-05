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

    // Sample phase only after the acquisition core has selected frequency.
    // CLKDIVR high on REF rising means divider leads: DN. Low means UP.
    // Delay the output window until the sampled direction can settle.
    wire direction_dn, sample_valid, logic1, logic0;
    wire [4:1] window_delay;
    wire capture_valid, pulse_window, up_logic, dn_logic;
    sky130_fd_sc_hd__conb_1 consts (`INTEGERPLL_SKY130_CELL_PG .HI(logic1), .LO(logic0));
    sky130_fd_sc_hd__dfrtp_1 direction_ff (`INTEGERPLL_SKY130_CELL_PG
        .CLK(REF), .D(CLKDIVR), .RESET_B(RESET_N), .Q(direction_dn));
    // Inhibit output until a reference edge has sampled a direction after reset.
    sky130_fd_sc_hd__dfrtp_1 valid_ff (`INTEGERPLL_SKY130_CELL_PG
        .CLK(REF), .D(logic1), .RESET_B(RESET_N), .Q(sample_valid));
    sky130_fd_sc_hd__dlygate4sd3_1 window_delay_0 (`INTEGERPLL_SKY130_CELL_PG .A(REF), .X(window_delay[1]));
    sky130_fd_sc_hd__dlygate4sd3_1 window_delay_1 (`INTEGERPLL_SKY130_CELL_PG .A(window_delay[1]), .X(window_delay[2]));
    sky130_fd_sc_hd__dlygate4sd3_1 window_delay_2 (`INTEGERPLL_SKY130_CELL_PG .A(window_delay[2]), .X(window_delay[3]));
    sky130_fd_sc_hd__dlygate4sd3_1 window_delay_3 (`INTEGERPLL_SKY130_CELL_PG .A(window_delay[3]), .X(window_delay[4]));
    sky130_fd_sc_hd__and2_1 valid_gate (`INTEGERPLL_SKY130_CELL_PG
        .A(sample_valid), .B(RESET_N), .X(capture_valid));
    sky130_fd_sc_hd__and2_1 window_gate (`INTEGERPLL_SKY130_CELL_PG
        .A(window_delay[4]), .B(capture_valid), .X(pulse_window));
    sky130_fd_sc_hd__and2b_1 up_gate (`INTEGERPLL_SKY130_CELL_PG
        .A_N(direction_dn), .B(pulse_window), .X(up_logic));
    sky130_fd_sc_hd__and2_1 dn_gate (`INTEGERPLL_SKY130_CELL_PG
        .A(direction_dn), .B(pulse_window), .X(dn_logic));
    sky130_fd_sc_hd__buf_8 up_out (`INTEGERPLL_SKY130_CELL_PG .A(up_logic), .X(BBPD[1]));
    sky130_fd_sc_hd__buf_8 dn_out (`INTEGERPLL_SKY130_CELL_PG .A(dn_logic), .X(BBPD[0]));
endmodule
`undef INTEGERPLL_SKY130_CELL_PG
`default_nettype wire
