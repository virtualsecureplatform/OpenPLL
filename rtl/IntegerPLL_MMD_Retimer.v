// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_MMD_Retimer #(
    parameter RATIO_WIDTH = 8,
    parameter REGISTER_CONFIG = 0,
    parameter COUNTDOWN = 0
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
    wire [RATIO_WIDTH-1:0] decremented_ratio = safe_ratio - 1'b1;
    // For the highest bit, subtract-one plus the ratio-zero clamp reduces
    // to this two-level expression. Avoid the clamp/subtractor carry path.
    wire [RATIO_WIDTH-1:0] decoded_terminal =
        {CLK_DIV_RATIO[RATIO_WIDTH-1] && (|CLK_DIV_RATIO[RATIO_WIDTH-2:0]),
         decremented_ratio[RATIO_WIDTH-2:0]};

    assign safe_ratio = (CLK_DIV_RATIO < 2) ?
        {{(RATIO_WIDTH-2){1'b0}}, 2'b10} : CLK_DIV_RATIO;
    generate
        if (REGISTER_CONFIG != 0) begin : gen_registered_config
            reg [RATIO_WIDTH-1:0] terminal_q, duty_q;
            always @(posedge DIV_IN or negedge RESET_N) begin
                if (!RESET_N) begin
                    terminal_q <= {{(RATIO_WIDTH-1){1'b0}},1'b1};
                    duty_q <= {{(RATIO_WIDTH-1){1'b0}},1'b1};
                end else begin
                    terminal_q <= decoded_terminal;
                    duty_q <= safe_ratio >> 1;
                end
            end
            assign terminal_count = terminal_q;
            assign duty_count = duty_q;
        end else begin : gen_direct_config
            assign terminal_count = decoded_terminal;
            assign duty_count = safe_ratio >> 1;
        end
    endgenerate

    generate if(COUNTDOWN != 0) begin : gen_countdown
        // Ratio changes take effect at the next wrap. Predict that wrap and
        // two-bit borrow boundaries before the counter update cycle.
        // Store the active phase with a low reset value. This avoids an
        // asynchronous-set flop on the high-fanout reload control.
        reg advance_active, borrow2, borrow4;
        reg wrap_soon;
        wire reload_pending = !advance_active;
        wire [13:0] high_mask, high_load;
        reg [13:0] high_shift;
        genvar high_bit;
        for(high_bit=0;high_bit<14;high_bit=high_bit+1) begin : gen_high_mask
            assign high_mask[high_bit]=(safe_ratio >> 1)>high_bit+1;
        end
        if(REGISTER_CONFIG != 0) begin : gen_high_config
            reg [13:0] mask_q;
            always @(posedge DIV_IN or negedge RESET_N)
                if(!RESET_N) mask_q<=0;
                else mask_q<=high_mask;
            assign high_load=mask_q;
        end else begin : gen_direct_high_config
            assign high_load=high_mask;
        end
        always @(posedge DIV_IN or negedge RESET_N) begin
            if(!RESET_N) begin
                counter<=0;advance_active<=0;borrow2<=0;borrow4<=0;
                wrap_soon<=0;
                high_shift<=0;clkdiv_raw<=0;CLKDIV_RETIMED<=0;
            end else begin
                CLKDIV_RETIMED<=clkdiv_raw;
                // Detect the wrap two cycles ahead; the next stage only
                // combines registered flags before driving the reload muxes.
                advance_active<=reload_pending || !wrap_soon;
                wrap_soon<=(advance_active && counter==2) ||
                           (reload_pending && terminal_count==1);
                // The reload itself supplies the first high clock. Shift
                // the remaining floor(ratio/2)-1 high clocks toward bit zero.
                // A live ratio change cannot shorten the pulse already loaded.
                clkdiv_raw<=reload_pending || high_shift[0];
                high_shift<=reload_pending ? high_load : (high_shift >> 1);
                if(reload_pending) begin
                    counter<=terminal_count;
                    borrow2<=terminal_count[1:0]==0;
                    borrow4<=terminal_count[3:0]==0;
                end else begin
                    counter[1:0]<=counter[1:0]-2'd1;
                    counter[3:2]<=counter[3:2]-{1'b0,borrow2};
                    counter[4]<=counter[4]^borrow4;
                    borrow2<=counter[1:0]==1;
                    borrow4<=counter[3:0]==1;
                end
            end
        end
        // synthesis translate_off
        initial if(RATIO_WIDTH!=5) $fatal(1,"countdown divider requires five-bit ratio");
        // synthesis translate_on
    end else begin : gen_upcounter
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
    end endgenerate

endmodule

`default_nettype wire
