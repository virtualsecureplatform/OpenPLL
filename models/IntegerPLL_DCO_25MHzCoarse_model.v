// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_DCO #(
    parameter THERM_INVERT = 1
) (
    input wire RESET_N,
`ifdef OPENPLL_DCO_MODEL_COARSE
    input wire [5:0] COARSEBINARY_CODE,
`endif
    input wire [254:0] DCO_THERM,
    output reg PLLOUT
);

    real half_period_ns;
    real freq_mhz;
    integer tune_count;
    integer dco_code;
`ifdef OPENPLL_DCO_MODEL_COARSE
    wire [5:0] coarse_code = COARSEBINARY_CODE;
`else
    wire [5:0] coarse_code = 6'd0;
`endif

    function integer count255;
        input [254:0] value;
        integer i;
        begin
            count255 = 0;
            for (i = 0; i < 255; i = i + 1)
                count255 = count255 + value[i];
        end
    endfunction

    function integer therm_to_code;
        input integer enabled_count;
        begin
            therm_to_code = THERM_INVERT ? (255 - enabled_count) : enabled_count;
        end
    endfunction

    function real interp;
        input integer code;
        input integer code_a;
        input real freq_a;
        input integer code_b;
        input real freq_b;
        begin
            interp = freq_a + (freq_b - freq_a) * (code - code_a) / (code_b - code_a);
        end
    endfunction

    function real c20_freq_mhz;
        input integer code;
        begin
            if (code <= 128)
                c20_freq_mhz = interp(code, 0, 98.609, 128, 100.515);
            else
                c20_freq_mhz = interp(code, 128, 100.515, 255, 101.817);
        end
    endfunction

    function real c06_freq_mhz;
        input integer code;
        begin
            if (code <= 128)
                c06_freq_mhz = interp(code, 0, 231.778, 128, 243.384);
            else if (code <= 192)
                c06_freq_mhz = interp(code, 128, 243.384, 192, 249.187);
            else if (code <= 224)
                c06_freq_mhz = interp(code, 192, 249.187, 224, 249.756);
            else if (code <= 234)
                c06_freq_mhz = interp(code, 224, 249.756, 234, 249.813);
            else
                c06_freq_mhz = interp(code, 234, 249.813, 255, 250.488);
        end
    endfunction

    function real c04_freq_mhz;
        input integer code;
        begin
            if (code <= 64)
                c04_freq_mhz = interp(code, 0, 285.172, 64, 295.760);
            else if (code <= 96)
                c04_freq_mhz = interp(code, 64, 295.760, 96, 301.054);
            else if (code <= 128)
                c04_freq_mhz = interp(code, 96, 301.054, 128, 304.371);
            else if (code <= 160)
                c04_freq_mhz = interp(code, 128, 304.371, 160, 308.390);
            else
                c04_freq_mhz = interp(code, 160, 308.390, 255, 320.321);
        end
    endfunction

    function real c02_freq_mhz;
        input integer code;
        begin
            if (code <= 32)
                c02_freq_mhz = interp(code, 0, 385.207, 32, 390.628);
            else if (code <= 64)
                c02_freq_mhz = interp(code, 32, 390.628, 64, 397.373);
            else if (code <= 96)
                c02_freq_mhz = interp(code, 64, 397.373, 96, 404.357);
            else if (code <= 128)
                c02_freq_mhz = interp(code, 96, 404.357, 128, 411.194);
            else if (code <= 192)
                c02_freq_mhz = interp(code, 128, 411.194, 192, 425.984);
            else
                c02_freq_mhz = interp(code, 192, 425.984, 255, 438.705);
        end
    endfunction

    function real coarse_freq_mhz;
        input [5:0] coarse;
        input integer code;
        begin
            case (coarse)
                6'd20: coarse_freq_mhz = c20_freq_mhz(code);
                6'd6: coarse_freq_mhz = c06_freq_mhz(code);
                6'd4: coarse_freq_mhz = c04_freq_mhz(code);
                6'd2: coarse_freq_mhz = c02_freq_mhz(code);
                default: coarse_freq_mhz = c20_freq_mhz(code);
            endcase
        end
    endfunction

    initial begin
        PLLOUT = 1'b0;
        half_period_ns = 5.0;
        freq_mhz = 100.0;
    end

    always @* begin
        tune_count = count255(DCO_THERM);
        dco_code = therm_to_code(tune_count);
        freq_mhz = coarse_freq_mhz(coarse_code, dco_code);
        half_period_ns = 500.0 / freq_mhz;
    end

    always begin
        if (!RESET_N) begin
            PLLOUT = 1'b0;
            @(posedge RESET_N);
        end else begin
            #(half_period_ns) PLLOUT = ~PLLOUT;
        end
    end

endmodule

`default_nettype wire
