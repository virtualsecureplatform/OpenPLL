`timescale 1ns/1ps
// Diagnostic timing boundary. The controller RTL remains unmodified.
// Trace DIVIDED_PHYSICAL; feed the detector after the additional wire delay.
module Prototype400ClockTiming(
    input wire REFCLK, DIVIDED_RTL, RESET_N,
    output wire REF_AT_DETECTOR, DIVIDED_PHYSICAL, FEEDBACK_AT_DETECTOR
);
    integer div_rise=0, div_fall=0, fb_rise=0, fb_fall=0, ref_rise=0, ref_fall=0;
    reg ref_delayed=0, div_delayed=0, fb_delayed=0;
    initial begin
        if (!$value$plusargs("clock_divided_output_rise_ps=%d",div_rise) ||
            !$value$plusargs("clock_divided_output_fall_ps=%d",div_fall) ||
            !$value$plusargs("clock_feedback_wire_rise_ps=%d",fb_rise) ||
            !$value$plusargs("clock_feedback_wire_fall_ps=%d",fb_fall) ||
            !$value$plusargs("clock_reference_wire_rise_ps=%d",ref_rise) ||
            !$value$plusargs("clock_reference_wire_fall_ps=%d",ref_fall))
            $fatal(1,"explicit clock timing parameters required");
        // The shortest bench reset lasts 10ns; flush every delayed event within it.
        if (div_rise<0 || div_fall<0 || fb_rise<0 || fb_fall<0 || ref_rise<0 || ref_fall<0 ||
            div_rise+fb_rise>=10000 || div_fall+fb_fall>=10000 || ref_rise>=10000 || ref_fall>=10000)
            $fatal(1,"clock timing outside diagnostic reset/transport contract");
    end
    always @(REFCLK) ref_delayed <= #(0.001*(REFCLK ? ref_rise : ref_fall)) REFCLK;
    always @(DIVIDED_RTL) div_delayed <= #(0.001*(DIVIDED_RTL ? div_rise : div_fall)) DIVIDED_RTL;
    assign DIVIDED_PHYSICAL = RESET_N ? div_delayed : 1'b0;
    always @(DIVIDED_PHYSICAL) fb_delayed <= #(0.001*(DIVIDED_PHYSICAL ? fb_rise : fb_fall)) DIVIDED_PHYSICAL;
    assign FEEDBACK_AT_DETECTOR = RESET_N ? fb_delayed : 1'b0;
    assign REF_AT_DETECTOR = ref_delayed;
endmodule
