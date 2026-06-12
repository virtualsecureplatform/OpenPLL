// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_B2TH #(
    parameter BIN_WIDTH = 5,
    parameter THERM_WIDTH = (1 << BIN_WIDTH) - 1,
    parameter INVERT_OUTPUT = 0
) (
    input wire [BIN_WIDTH-1:0] binary_code,
    output wire [THERM_WIDTH-1:0] thermal_code
);

    genvar i;
    generate
        for (i = 0; i < THERM_WIDTH; i = i + 1) begin : gen_therm
            wire active;

            assign active = (binary_code > i);
            assign thermal_code[i] = INVERT_OUTPUT ? ~active : active;
        end
    endgenerate

endmodule

`default_nettype wire
