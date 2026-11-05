// Exact candidate boundary for a future validated DCO/interface model.
// External clocks and BBPD inputs do not themselves qualify analog behavior.
`timescale 1ns/1ps
module IntegerPLL_ReleaseHarness (
    input wire REFCLK, PLLOUT, RESET_N, PLL_ENABLE,
    input wire [4:0] MODE_DIVIDER,
    input wire [1:0] BBPD,
    input wire [7:0] KI,
    input wire [4:0] KP,
    output wire CLKDIV_RETIMED, BBPD_RESET_N, TRACKING, CONFIG_BUSY, FAILED,
    output wire [5:0] COARSE_CODE,
    output wire [7:0] DCO_CODE,
    output wire [9:0] DLF_CODE
);
    IntegerPLL_AcquiringCore #(.DLF_UPDATE_ON_PLLOUT(0)) candidate (
        .REFCLK(REFCLK), .PLLOUT(PLLOUT), .RESET_N(RESET_N),
        .PLL_ENABLE(PLL_ENABLE), .FEEDBACK_DIVIDER(MODE_DIVIDER),
        .BBPD(BBPD), .KI(KI), .KP(KP),
        .CLKDIV_RETIMED(CLKDIV_RETIMED), .BBPD_RESET_N(BBPD_RESET_N),
        .TRACKING(TRACKING), .CONFIG_BUSY(CONFIG_BUSY), .FAILED(FAILED),
        .COARSE_CODE(COARSE_CODE), .DCO_CODE(DCO_CODE), .DLF_CODE(DLF_CODE),
        .COARSETHERMAL_CODE(), .DCO_THERM()
    );
endmodule
