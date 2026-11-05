// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_Divider (
    input wire CLK,
    input wire RESET_N,
    output reg PLLOUT_DIV
);

    reg [3:0] half_count;

    always @(posedge CLK or negedge RESET_N) begin
        if (!RESET_N) begin
            half_count <= 4'd0;
            PLLOUT_DIV <= 1'b0;
        end else if (half_count == 4'd15) begin
            half_count <= 4'd0;
            PLLOUT_DIV <= ~PLLOUT_DIV;
        end else begin
            half_count <= half_count + 4'd1;
        end
    end

endmodule

`default_nettype wire
