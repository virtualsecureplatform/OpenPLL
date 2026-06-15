// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_25MHzModeConfig #(
    parameter CODE_WIDTH = 10,
    parameter DCO_CODE_WIDTH = 8,
    parameter GAIN_WIDTH = 8,
    parameter KP_WIDTH = 5,
    parameter FEEDBACK_DIVIDER_WIDTH = 5
) (
    input wire [FEEDBACK_DIVIDER_WIDTH-1:0] FEEDBACK_DIVIDER,
    output reg [7:0] MMDCLKDIV_RATIO,
    output reg [5:0] COARSEBINARY_CODE,
    output reg [CODE_WIDTH-1:0] DLF_Ext_Data,
    output reg [GAIN_WIDTH-1:0] DLF_KI,
    output reg [KP_WIDTH-1:0] DLF_KP,
    output reg [15:0] TARGET_MHZ,
    output reg [7:0] TARGET_DCO_CODE,
    output reg CONFIG_VALID
);

    localparam integer DCO_CODE_SHIFT = CODE_WIDTH - DCO_CODE_WIDTH;

    localparam [FEEDBACK_DIVIDER_WIDTH-1:0] DIV_100MHZ = 5'd4;
    localparam [FEEDBACK_DIVIDER_WIDTH-1:0] DIV_250MHZ = 5'd10;
    localparam [FEEDBACK_DIVIDER_WIDTH-1:0] DIV_300MHZ = 5'd12;
    localparam [FEEDBACK_DIVIDER_WIDTH-1:0] DIV_400MHZ = 5'd16;
    localparam [FEEDBACK_DIVIDER_WIDTH-1:0] DIV_500MHZ = 5'd20;

    function [CODE_WIDTH-1:0] seed_word;
        input [DCO_CODE_WIDTH-1:0] dco_code;
        begin
            seed_word = {{(CODE_WIDTH-DCO_CODE_WIDTH){1'b0}}, dco_code}
                        << DCO_CODE_SHIFT;
        end
    endfunction

    always @* begin
        DLF_KI = {{(GAIN_WIDTH-3){1'b0}}, 3'd4};
        DLF_KP = {{(KP_WIDTH-2){1'b0}}, 2'd2};
        CONFIG_VALID = 1'b1;

        case (FEEDBACK_DIVIDER)
            DIV_100MHZ: begin
                TARGET_MHZ = 16'd100;
                MMDCLKDIV_RATIO = 8'd4;
                COARSEBINARY_CODE = 6'd24;
                TARGET_DCO_CODE = 8'd139;
                DLF_Ext_Data = seed_word(8'd139);
                DLF_KI = {{(GAIN_WIDTH-3){1'b0}}, 3'd4};
                DLF_KP = {{(KP_WIDTH-2){1'b0}}, 2'd2};
            end
            DIV_250MHZ: begin
                TARGET_MHZ = 16'd250;
                MMDCLKDIV_RATIO = 8'd10;
                COARSEBINARY_CODE = 6'd7;
                TARGET_DCO_CODE = 8'd8;
                DLF_Ext_Data = seed_word(8'd8);
                DLF_KI = {{(GAIN_WIDTH-3){1'b0}}, 3'd4};
                DLF_KP = {{(KP_WIDTH-2){1'b0}}, 2'd2};
            end
            DIV_300MHZ: begin
                TARGET_MHZ = 16'd300;
                MMDCLKDIV_RATIO = 8'd12;
                COARSEBINARY_CODE = 6'd6;
                TARGET_DCO_CODE = 8'd242;
                DLF_Ext_Data = seed_word(8'd242);
                DLF_KI = {{(GAIN_WIDTH-3){1'b0}}, 3'd4};
                DLF_KP = {{(KP_WIDTH-2){1'b0}}, 2'd2};
            end
            DIV_400MHZ: begin
                TARGET_MHZ = 16'd400;
                MMDCLKDIV_RATIO = 8'd16;
                COARSEBINARY_CODE = 6'd3;
                TARGET_DCO_CODE = 8'd45;
                DLF_Ext_Data = seed_word(8'd45);
                DLF_KI = {{(GAIN_WIDTH-3){1'b0}}, 3'd4};
                DLF_KP = {{(KP_WIDTH-2){1'b0}}, 2'd2};
            end
            DIV_500MHZ: begin
                TARGET_MHZ = 16'd500;
                MMDCLKDIV_RATIO = 8'd20;
                COARSEBINARY_CODE = 6'd2;
                TARGET_DCO_CODE = 8'd149;
                DLF_Ext_Data = seed_word(8'd149);
                DLF_KI = {{(GAIN_WIDTH-3){1'b0}}, 3'd4};
                DLF_KP = {{(KP_WIDTH-2){1'b0}}, 2'd2};
            end
            default: begin
                TARGET_MHZ = 16'd0;
                MMDCLKDIV_RATIO = {{(8-FEEDBACK_DIVIDER_WIDTH){1'b0}}, FEEDBACK_DIVIDER};
                COARSEBINARY_CODE = 6'd0;
                TARGET_DCO_CODE = 8'd0;
                DLF_Ext_Data = {CODE_WIDTH{1'b0}};
                CONFIG_VALID = 1'b0;
            end
        endcase
    end

endmodule

`default_nettype wire
