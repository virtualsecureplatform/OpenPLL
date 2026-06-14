// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_25MHzModeConfig #(
    parameter CODE_WIDTH = 10,
    parameter DCO_CODE_WIDTH = 8,
    parameter GAIN_WIDTH = 8
) (
    input wire [1:0] MODE_SELECT,
    output reg [7:0] MMDCLKDIV_RATIO,
    output reg [5:0] COARSEBINARY_CODE,
    output reg [CODE_WIDTH-1:0] DLF_Ext_Data,
    output reg [GAIN_WIDTH-1:0] DLF_KI,
    output reg [GAIN_WIDTH-1:0] DLF_KP,
    output reg [15:0] TARGET_MHZ,
    output reg [7:0] TARGET_DCO_CODE
);

    localparam integer DCO_CODE_SHIFT = CODE_WIDTH - DCO_CODE_WIDTH;

    localparam [1:0] MODE_100MHZ = 2'd0;
    localparam [1:0] MODE_250MHZ = 2'd1;
    localparam [1:0] MODE_300MHZ = 2'd2;
    localparam [1:0] MODE_400MHZ = 2'd3;

    function [CODE_WIDTH-1:0] seed_word;
        input [DCO_CODE_WIDTH-1:0] dco_code;
        begin
            seed_word = {{(CODE_WIDTH-DCO_CODE_WIDTH){1'b0}}, dco_code}
                        << DCO_CODE_SHIFT;
        end
    endfunction

    always @* begin
        DLF_KI = {{(GAIN_WIDTH-5){1'b0}}, 5'd16};
        DLF_KP = {{(GAIN_WIDTH-3){1'b0}}, 3'd4};

        case (MODE_SELECT)
            MODE_100MHZ: begin
                TARGET_MHZ = 16'd100;
                MMDCLKDIV_RATIO = 8'd4;
                COARSEBINARY_CODE = 6'd20;
                TARGET_DCO_CODE = 8'd93;
                DLF_Ext_Data = seed_word(8'd93);
            end
            MODE_250MHZ: begin
                TARGET_MHZ = 16'd250;
                MMDCLKDIV_RATIO = 8'd10;
                COARSEBINARY_CODE = 6'd6;
                TARGET_DCO_CODE = 8'd234;
                DLF_Ext_Data = seed_word(8'd234);
            end
            MODE_300MHZ: begin
                TARGET_MHZ = 16'd300;
                MMDCLKDIV_RATIO = 8'd12;
                COARSEBINARY_CODE = 6'd4;
                TARGET_DCO_CODE = 8'd90;
                DLF_Ext_Data = seed_word(8'd90);
            end
            default: begin
                TARGET_MHZ = 16'd400;
                MMDCLKDIV_RATIO = 8'd16;
                COARSEBINARY_CODE = 6'd2;
                TARGET_DCO_CODE = 8'd76;
                DLF_Ext_Data = seed_word(8'd76);
            end
        endcase
    end

endmodule

`default_nettype wire
