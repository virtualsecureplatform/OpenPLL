// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_MMD_Retimer #(
    parameter RATIO_WIDTH = 8
) (
    input wire DIV_IN,
    input wire RESET_N,
    input wire [RATIO_WIDTH-1:0] CLK_DIV_RATIO,
    output reg CLKDIV_RETIMED
);

    reg [RATIO_WIDTH-1:0] counter;
    reg clkdiv_raw;

    wire [RATIO_WIDTH-1:0] safe_ratio;
    wire [RATIO_WIDTH-1:0] terminal_count;
    wire [RATIO_WIDTH-1:0] duty_count;

    assign safe_ratio = (CLK_DIV_RATIO < 2) ?
        {{(RATIO_WIDTH-2){1'b0}}, 2'b10} : CLK_DIV_RATIO;
    assign terminal_count = safe_ratio - {{(RATIO_WIDTH-1){1'b0}}, 1'b1};
    assign duty_count = safe_ratio >> 1;

    always @(posedge DIV_IN or negedge RESET_N) begin
        if (!RESET_N) begin
            counter <= {RATIO_WIDTH{1'b0}};
            clkdiv_raw <= 1'b0;
            CLKDIV_RETIMED <= 1'b0;
        end else begin
            if (counter >= terminal_count)
                counter <= {RATIO_WIDTH{1'b0}};
            else
                counter <= counter + {{(RATIO_WIDTH-1){1'b0}}, 1'b1};

            clkdiv_raw <= (counter < duty_count);
            CLKDIV_RETIMED <= clkdiv_raw;
        end
    end

endmodule

`default_nettype wire
