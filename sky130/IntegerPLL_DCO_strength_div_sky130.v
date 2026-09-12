// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental strength-tuned ring and /1,/2,/4,/8 output. Qualification pending.
// Each 12-code coarse group selects 63,53,44,37,31,26,22,18,15,13,11,9
// parallel inverters per stage. All 255 fine loads remain independently controlled.
module IntegerPLL_DCO_STRENGTH_DIV (
`ifdef USE_POWER_PINS
    inout wire VPWR,VGND,VPB,VNB,
`endif
    input wire RESET_N,
    input wire [46:0] COARSETHERMAL_CODE,
    input wire [254:0] DCO_THERM,
    output wire PLLOUT
);
`ifndef USE_POWER_PINS
    supply1 VPWR,VPB;
    supply0 VGND,VNB;
`endif
`ifdef USE_CELL_POWER_PINS
`define STRENGTH_PG .VPWR(VPWR),.VGND(VGND),.VPB(VPB),.VNB(VNB),
`else
`define STRENGTH_PG
`endif
    (* keep="true" *) wire osc_node,stage1,stage2;
    wire [10:0] strength_enable,select0,select1,select2,enable_raw;
    wire [254:0] load_dummy;
    wire [2:0] divided,divider_d;
    wire mux0,mux1,mux2;
    function integer strength_tier;
        input integer index;
        begin
            if(index<11) strength_tier=10;
            else if(index<13) strength_tier=9;
            else if(index<15) strength_tier=8;
            else if(index<18) strength_tier=7;
            else if(index<22) strength_tier=6;
            else if(index<26) strength_tier=5;
            else if(index<31) strength_tier=4;
            else if(index<37) strength_tier=3;
            else if(index<44) strength_tier=2;
            else if(index<53) strength_tier=1;
            else strength_tier=0;
        end
    endfunction

    sky130_fd_sc_hd__nand2_1 osc_gate (`STRENGTH_PG
        .A(stage2),.B(RESET_N),.Y(osc_node));
    sky130_fd_sc_hd__inv_1 stage1_gate (`STRENGTH_PG .A(osc_node),.Y(stage1));
    sky130_fd_sc_hd__inv_1 stage2_gate (`STRENGTH_PG .A(stage1),.Y(stage2));

    genvar j,i,f;
    generate for(j=0;j<11;j=j+1) begin: gen_strength
        sky130_fd_sc_hd__mux2_1 select_group0 (`STRENGTH_PG
            .A0(COARSETHERMAL_CODE[j]),.A1(COARSETHERMAL_CODE[j+12]),
            .S(COARSETHERMAL_CODE[11]),.X(select0[j]));
        sky130_fd_sc_hd__mux2_1 select_group1 (`STRENGTH_PG
            .A0(select0[j]),.A1(COARSETHERMAL_CODE[j+24]),
            .S(COARSETHERMAL_CODE[23]),.X(select1[j]));
        sky130_fd_sc_hd__mux2_1 select_group2 (`STRENGTH_PG
            .A0(select1[j]),.A1(COARSETHERMAL_CODE[j+36]),
            .S(COARSETHERMAL_CODE[35]),.X(select2[j]));
        sky130_fd_sc_hd__inv_1 enable_inverter (`STRENGTH_PG
            .A(select2[j]),.Y(enable_raw[j]));
        // Explicit reset gating permits a structural proof that the reset NAND
        // cannot contend with a parallel inverter while RESET_N is low.
        (* keep="true", dont_touch="true" *)
        sky130_fd_sc_hd__and2_4 reset_gate (`STRENGTH_PG
            .A(RESET_N),.B(enable_raw[j]),.X(strength_enable[j]));
    end
    for(i=0;i<63;i=i+1) begin: gen_drive
        (* keep="true", dont_touch="true" *)
        sky130_fd_sc_hd__einvp_1 osc_driver (`STRENGTH_PG
            .A(stage2),.TE(i<9 ? RESET_N : strength_enable[strength_tier(i)]),.Z(osc_node));
        (* keep="true", dont_touch="true" *)
        sky130_fd_sc_hd__einvp_1 stage1_driver (`STRENGTH_PG
            .A(osc_node),.TE(i<9 ? RESET_N : strength_enable[strength_tier(i)]),.Z(stage1));
        (* keep="true", dont_touch="true" *)
        sky130_fd_sc_hd__einvp_1 stage2_driver (`STRENGTH_PG
            .A(stage1),.TE(i<9 ? RESET_N : strength_enable[strength_tier(i)]),.Z(stage2));
    end
    for(f=0;f<255;f=f+1) begin: gen_load
        sky130_fd_sc_hd__einvp_1 load (`STRENGTH_PG
            .A((f%2)==0 ? osc_node : stage2),.TE(DCO_THERM[f]),.Z(load_dummy[f]));
    end
    for(j=0;j<3;j=j+1) begin: gen_divider
        sky130_fd_sc_hd__inv_1 feedback (`STRENGTH_PG
            .A(divided[j]),.Y(divider_d[j]));
        if(j==0) begin: first
            sky130_fd_sc_hd__dfrtp_1 toggle (`STRENGTH_PG
                .CLK(osc_node),.D(divider_d[j]),.RESET_B(RESET_N),.Q(divided[j]));
        end else begin: following
            sky130_fd_sc_hd__dfrtp_1 toggle (`STRENGTH_PG
                .CLK(divided[j-1]),.D(divider_d[j]),.RESET_B(RESET_N),.Q(divided[j]));
        end
    end endgenerate
    sky130_fd_sc_hd__mux2_4 output_select0 (`STRENGTH_PG
        .A0(osc_node),.A1(divided[0]),.S(COARSETHERMAL_CODE[11]),.X(mux0));
    sky130_fd_sc_hd__mux2_4 output_select1 (`STRENGTH_PG
        .A0(mux0),.A1(divided[1]),.S(COARSETHERMAL_CODE[23]),.X(mux1));
    sky130_fd_sc_hd__mux2_4 output_select2 (`STRENGTH_PG
        .A0(mux1),.A1(divided[2]),.S(COARSETHERMAL_CODE[35]),.X(mux2));
    sky130_fd_sc_hd__buf_1 output_buffer (`STRENGTH_PG .A(mux2),.X(PLLOUT));
endmodule
`undef STRENGTH_PG
`default_nettype wire
