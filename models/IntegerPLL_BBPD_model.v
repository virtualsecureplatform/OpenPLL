// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_BBPD (
    input wire REF,
    input wire CLKDIVR,
    input wire RESET_N,
    output wire [1:0] BBPD
);

    reg up_q;
    reg dn_q;

    wire reset_request;
    wire reset_delayed;

    assign reset_request = up_q & dn_q;
    assign #0.2 reset_delayed = reset_request;
    assign BBPD = {up_q, dn_q};

    always @(posedge REF or negedge RESET_N or posedge reset_delayed) begin
        if (!RESET_N || reset_delayed)
            up_q <= 1'b0;
        else
            up_q <= 1'b1;
    end

    always @(posedge CLKDIVR or negedge RESET_N or posedge reset_delayed) begin
        if (!RESET_N || reset_delayed)
            dn_q <= 1'b0;
        else
            dn_q <= 1'b1;
    end

    initial begin
        up_q = 1'b0;
        dn_q = 1'b0;
    end

endmodule

`default_nettype wire
