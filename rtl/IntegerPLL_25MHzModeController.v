// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_25MHzModeController #(
    parameter CODE_WIDTH = 10,
    parameter DCO_CODE_WIDTH = 8,
    parameter GAIN_WIDTH = 8,
    parameter CLEAR_CYCLES = 4
) (
    input wire CLKDIV_RETIMED,
    input wire RESET_N,
    input wire PLL_ENABLE,
    input wire [1:0] MODE_SELECT,
    output wire DLF_En,
    output wire DLF_Clear,
    output wire DLF_Ext_Override,
    output wire DLF_IN_POL,
    output wire [CODE_WIDTH-1:0] DLF_Ext_Data,
    output wire [GAIN_WIDTH-1:0] DLF_KI,
    output wire [GAIN_WIDTH-1:0] DLF_KP,
    output wire [5:0] COARSEBINARY_CODE,
    output wire [7:0] MMDCLKDIV_RATIO,
    output wire CONFIG_BUSY,
    output wire TRACKING,
    output wire [15:0] TARGET_MHZ,
    output wire [7:0] TARGET_DCO_CODE
);

    localparam [1:0] STATE_IDLE = 2'd0;
    localparam [1:0] STATE_LOAD = 2'd1;
    localparam [1:0] STATE_TRACK = 2'd2;
    localparam integer CLEAR_LIMIT = (CLEAR_CYCLES < 1) ? 1 : CLEAR_CYCLES;
    localparam integer CLEAR_COUNT_WIDTH =
        (CLEAR_LIMIT <= 1) ? 1 : $clog2(CLEAR_LIMIT + 1);

    reg [1:0] state;
    reg [1:0] mode_latched;
    reg [CLEAR_COUNT_WIDTH-1:0] clear_count;

    wire load_active;
    wire track_active;

    assign load_active = (state == STATE_LOAD) && PLL_ENABLE;
    assign track_active = (state == STATE_TRACK) && PLL_ENABLE;

    assign DLF_En = track_active;
    assign DLF_Clear = load_active;
    assign DLF_Ext_Override = 1'b0;
    assign DLF_IN_POL = 1'b1;
    assign CONFIG_BUSY = PLL_ENABLE && (state != STATE_TRACK);
    assign TRACKING = track_active;

    IntegerPLL_25MHzModeConfig #(
        .CODE_WIDTH(CODE_WIDTH),
        .DCO_CODE_WIDTH(DCO_CODE_WIDTH),
        .GAIN_WIDTH(GAIN_WIDTH)
    ) mode_config (
        .MODE_SELECT(mode_latched),
        .MMDCLKDIV_RATIO(MMDCLKDIV_RATIO),
        .COARSEBINARY_CODE(COARSEBINARY_CODE),
        .DLF_Ext_Data(DLF_Ext_Data),
        .DLF_KI(DLF_KI),
        .DLF_KP(DLF_KP),
        .TARGET_MHZ(TARGET_MHZ),
        .TARGET_DCO_CODE(TARGET_DCO_CODE)
    );

    always @(posedge CLKDIV_RETIMED or negedge RESET_N) begin
        if (!RESET_N) begin
            state <= STATE_IDLE;
            mode_latched <= 2'd0;
            clear_count <= {CLEAR_COUNT_WIDTH{1'b0}};
        end else begin
            case (state)
                STATE_IDLE: begin
                    clear_count <= {CLEAR_COUNT_WIDTH{1'b0}};
                    if (PLL_ENABLE) begin
                        state <= STATE_LOAD;
                        mode_latched <= MODE_SELECT;
                    end
                end

                STATE_LOAD: begin
                    if (!PLL_ENABLE) begin
                        state <= STATE_IDLE;
                        clear_count <= {CLEAR_COUNT_WIDTH{1'b0}};
                    end else if (clear_count == (CLEAR_LIMIT - 1)) begin
                        state <= STATE_TRACK;
                        clear_count <= {CLEAR_COUNT_WIDTH{1'b0}};
                    end else begin
                        clear_count <= clear_count + 1'b1;
                    end
                end

                STATE_TRACK: begin
                    clear_count <= {CLEAR_COUNT_WIDTH{1'b0}};
                    if (!PLL_ENABLE) begin
                        state <= STATE_IDLE;
                    end else if (MODE_SELECT != mode_latched) begin
                        state <= STATE_LOAD;
                        mode_latched <= MODE_SELECT;
                    end
                end

                default: begin
                    state <= STATE_IDLE;
                    clear_count <= {CLEAR_COUNT_WIDTH{1'b0}};
                end
            endcase
        end
    end

endmodule

`default_nettype wire
