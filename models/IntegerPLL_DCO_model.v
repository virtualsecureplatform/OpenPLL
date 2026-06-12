// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_DCO #(
    parameter THERM_INVERT = 1
) (
    input wire RESET_N,
    input wire [254:0] DCO_THERM,
    output reg PLLOUT
);

    real half_period_ns;
    real freq_mhz;
    real f0_mhz;
    real f64_mhz;
    real f128_mhz;
    real f192_mhz;
    real f255_mhz;
    integer tune_count;
    integer dco_code;
    integer use_piecewise5;

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

    function real piecewise5_freq_mhz;
        input integer code;
        begin
            if (code <= 64)
                piecewise5_freq_mhz = f0_mhz + (f64_mhz - f0_mhz) * code / 64.0;
            else if (code <= 128)
                piecewise5_freq_mhz = f64_mhz + (f128_mhz - f64_mhz) * (code - 64) / 64.0;
            else if (code <= 192)
                piecewise5_freq_mhz = f128_mhz + (f192_mhz - f128_mhz) * (code - 128) / 64.0;
            else
                piecewise5_freq_mhz = f192_mhz + (f255_mhz - f192_mhz) * (code - 192) / 63.0;
        end
    endfunction

    initial begin
        PLLOUT = 1'b0;
        half_period_ns = 8.0;
        freq_mhz = 62.5;
        f0_mhz = 46.25672588520797;
        f64_mhz = 47.95039109460694;
        f128_mhz = 49.762117807733404;
        f192_mhz = 51.61843654151962;
        f255_mhz = 52.34983089216307;
        use_piecewise5 = 0;
        if (!$value$plusargs("DCO_USE_PIECEWISE5=%d", use_piecewise5))
            use_piecewise5 = 0;
        if (!$value$plusargs("DCO_F0_MHZ=%f", f0_mhz))
            f0_mhz = 46.25672588520797;
        if (!$value$plusargs("DCO_F64_MHZ=%f", f64_mhz))
            f64_mhz = 47.95039109460694;
        if (!$value$plusargs("DCO_F128_MHZ=%f", f128_mhz))
            f128_mhz = 49.762117807733404;
        if (!$value$plusargs("DCO_F192_MHZ=%f", f192_mhz))
            f192_mhz = 51.61843654151962;
        if (!$value$plusargs("DCO_F255_MHZ=%f", f255_mhz))
            f255_mhz = 52.34983089216307;
    end

    always @* begin
        tune_count = count255(DCO_THERM);
        dco_code = therm_to_code(tune_count);
        if (use_piecewise5) begin
            freq_mhz = piecewise5_freq_mhz(dco_code);
            half_period_ns = 500.0 / freq_mhz;
        end else begin
            half_period_ns = 3.0 + (0.015 * tune_count);
            freq_mhz = 500.0 / half_period_ns;
        end
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
