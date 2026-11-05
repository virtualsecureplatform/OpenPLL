// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Reference-domain acquisition engine. Integration must transfer the stable
// coarse/seed bundle into the DCO domain before releasing the fine loop.
// RUN_FINE means handoff is ready, not that phase lock has been established.
module IntegerPLL_FrequencyAcquisition #(
    parameter integer COARSE_BANDS = 48,
    parameter integer SCAN_CYCLES = 32,
    parameter integer ENDPOINT_CYCLES = 128,
    parameter integer SETTLE_CYCLES = 4,
    parameter integer LOAD_CYCLES = 4,
    // Three detection windows plus worst-case acquisition must leave room for
    // BBPD settling and four acceptance windows inside the 200 us deadline.
    parameter integer MONITOR_CYCLES = 256,
    parameter integer FINE_CODE_ON_FINECLK = 0
) (
    input wire REFCLK,
    input wire PLLOUT,
    input wire RESET_N,
    input wire DCO_RESET_N,
    input wire PLL_ENABLE,
    input wire [4:0] FEEDBACK_DIVIDER,
    input wire [7:0] FINE_CODE,
    input wire TUNING_APPLIED,
    output reg [5:0] COARSE_CODE,
    output reg [7:0] FINE_SEED,
    output reg FINE_INCREASING,
    output wire RUN_FINE,
    output wire BUSY,
    output wire FAILED,
    input wire FINECLK,
    input wire FINE_RESET_N
);
    localparam [3:0] IDLE=0, SCAN_SETTLE=1, SCAN=2, PICK=3,
        LOW_SETTLE=4, LOW=5, HIGH_SETTLE=6, HIGH=7, CHOOSE=8,
        LOAD=9, TRACK=10, FAIL=11, SEED_DIVIDE=12;
    reg [3:0] state;
    reg [15:0] dco_count, dco_gray;
    // Predict each nibble carry one cycle ahead. This keeps the oscillator
    // counter and its registered Gray encoding off a 16-bit carry chain.
    reg carry4, carry8, carry12;
    wire [3:0] next0=dco_count[3:0]+4'd1;
    wire [3:0] next1=dco_count[7:4]+{3'b000,carry4};
    wire [3:0] next2=dco_count[11:8]+{3'b000,carry8};
    wire [3:0] next3=dco_count[15:12]+{3'b000,carry12};
    wire [15:0] next_dco_count={next3,next2,next1,next0};
    // Gray bit i flips when the binary carry reaches i but stops there.
    // Reuse predicted nibble carries instead of encoding the incremented
    // binary word through a second XOR level. The MSB flips on carry alone.
    wire [15:0] gray_increment;
    genvar gray_bit;
    generate for(gray_bit=0;gray_bit<16;gray_bit=gray_bit+1) begin : gen_gray_increment
        localparam integer BASE=(gray_bit/4)*4;
        wire nibble_carry;
        wire bit_carry;
        if(BASE==0) assign nibble_carry=1'b1;
        else if(BASE==4) assign nibble_carry=carry4;
        else if(BASE==8) assign nibble_carry=carry8;
        else assign nibble_carry=carry12;
        if(gray_bit==BASE) assign bit_carry=nibble_carry;
        else assign bit_carry=nibble_carry && (&dco_count[gray_bit-1:BASE]);
        if(gray_bit==15) assign gray_increment[gray_bit]=bit_carry;
        else assign gray_increment[gray_bit]=bit_carry && !dco_count[gray_bit];
    end endgenerate
    reg dco_rail;
    (* ASYNC_REG = "TRUE" *) reg [15:0] gray_meta, gray_sync;
    (* ASYNC_REG = "TRUE" *) reg rail_meta, rail_sync;
    reg [15:0] synchronized_count;
    reg [15:0] start_count, low_count, high_count;
    reg [15:0] cycles, endpoint_window;
    reg [9:0] apply_wait;
    reg [4:0] divider;
    reg [15:0] best_error [0:2];
    reg [5:0] best_band [0:2];
    reg [1:0] candidate;
    reg bad_monitor;
    integer bit_index;
    wire valid_mode = FEEDBACK_DIVIDER==4 || FEEDBACK_DIVIDER==10 ||
        FEEDBACK_DIVIDER==12 || FEEDBACK_DIVIDER==16 || FEEDBACK_DIVIDER==18;
    wire [15:0] elapsed_edges = synchronized_count-start_count;
    wire [15:0] scan_target = divider*SCAN_CYCLES[15:0];
    wire [15:0] scan_error = elapsed_edges>scan_target ?
        elapsed_edges-scan_target : scan_target-elapsed_edges;
    wire [15:0] endpoint_target = divider*endpoint_window;
    wire ascending = high_count>low_count;
    wire [15:0] lower_count = ascending ? low_count : high_count;
    wire [15:0] upper_count = ascending ? high_count : low_count;
    wire bracket = upper_count>lower_count+4 &&
        endpoint_target>=lower_count+2 && endpoint_target+2<=upper_count;
    wire [31:0] seed_numerator = ascending ?
        ({16'b0,endpoint_target}-{16'b0,low_count})*32'd239 : ({16'b0,low_count}-{16'b0,endpoint_target})*32'd239;
    wire [15:0] count_span = upper_count-lower_count;
    // A combinational 32/16 divider exceeds the 40 ns reference period.
    // Restoring division preserves the integer interpolation in 32 clocks.
    reg [31:0] seed_dividend, seed_quotient;
    reg [15:0] seed_remainder, seed_divisor;
    reg [5:0] seed_iterations;
    wire [16:0] seed_trial = {seed_remainder,seed_dividend[31]};
    wire seed_subtract = seed_trial>={1'b0,seed_divisor};
    wire [16:0] seed_next_remainder = seed_subtract ?
        seed_trial-{1'b0,seed_divisor} : seed_trial;
    wire [31:0] seed_next_quotient = {seed_quotient[30:0],seed_subtract};
    wire [31:0] interpolated_seed = 32'd8+seed_next_quotient;
    wire [15:0] monitor_target = divider*MONITOR_CYCLES[15:0];
    wire [15:0] monitor_error = elapsed_edges>monitor_target ?
        elapsed_edges-monitor_target : monitor_target-elapsed_edges;
    wire monitor_bad = monitor_error>monitor_target/50+2 || rail_sync;
    assign RUN_FINE = state==TRACK && PLL_ENABLE && valid_mode && FEEDBACK_DIVIDER==divider;
    assign BUSY = PLL_ENABLE && !RUN_FINE;
    assign FAILED = state==FAIL;

    // synthesis translate_off
    initial begin
        if(COARSE_BANDS<1 || COARSE_BANDS>48 || SCAN_CYCLES<1 || SCAN_CYCLES>3276 ||
           ENDPOINT_CYCLES<1 || ENDPOINT_CYCLES>1638 || SETTLE_CYCLES<4 ||
           SETTLE_CYCLES>65535 || LOAD_CYCLES<1 || LOAD_CYCLES>65535 ||
           MONITOR_CYCLES<4 || MONITOR_CYCLES>3276)
            $fatal(1,"invalid acquisition counter/settling parameters");
    end
    // synthesis translate_on

    always @(posedge PLLOUT or negedge DCO_RESET_N) begin
        if (!DCO_RESET_N) begin
            dco_count<=0; dco_gray<=0;
            carry4<=0;carry8<=0;carry12<=0;
        end
        else begin
            dco_count<=next_dco_count;
            dco_gray<=dco_gray^gray_increment;
            carry4<=dco_count[3:0]==4'he;
            carry8<=dco_count[7:0]==8'hfe;
            carry12<=dco_count[11:0]==12'hffe;
        end
    end
    // Decode the registered tuning word on its owning clock, then use the
    // existing two-stage reference receiver for the single rail flag.
    wire rail_clk=(FINE_CODE_ON_FINECLK!=0) ? FINECLK : PLLOUT;
    wire rail_reset_n=(FINE_CODE_ON_FINECLK!=0) ? FINE_RESET_N : DCO_RESET_N;
    always @(posedge rail_clk or negedge rail_reset_n)
        if(!rail_reset_n) dco_rail<=0;
        else dco_rail<=FINE_CODE==0 || FINE_CODE==255;
    always @(posedge REFCLK or negedge RESET_N) begin
        if (!RESET_N) begin gray_meta<=0; gray_sync<=0; rail_meta<=0;rail_sync<=0;end
        else begin
            gray_meta<=dco_gray; gray_sync<=gray_meta;
            rail_meta<=dco_rail; rail_sync<=rail_meta;
        end
    end
    always @* begin
        synchronized_count[15]=gray_sync[15];
        for(bit_index=14;bit_index>=0;bit_index=bit_index-1)
            synchronized_count[bit_index]=synchronized_count[bit_index+1]^gray_sync[bit_index];
    end

    always @(posedge REFCLK or negedge RESET_N) begin
        if (!RESET_N) begin
            state<=IDLE; COARSE_CODE<=0; FINE_SEED<=128;FINE_INCREASING<=1;divider<=0;
            cycles<=0; start_count<=0; low_count<=0; high_count<=0;
            apply_wait<=0;
            seed_dividend<=0;seed_quotient<=0;seed_remainder<=0;
            seed_divisor<=0;seed_iterations<=0;
            endpoint_window<=ENDPOINT_CYCLES[15:0]; candidate<=0; bad_monitor<=0;
            best_error[0]<=16'hffff; best_error[1]<=16'hffff; best_error[2]<=16'hffff;
            best_band[0]<=0; best_band[1]<=0; best_band[2]<=0;
        end else if (!PLL_ENABLE || !valid_mode) begin
            state<=IDLE; cycles<=0; bad_monitor<=0;apply_wait<=0;
        end else if (state==IDLE || FEEDBACK_DIVIDER!=divider) begin
            divider<=FEEDBACK_DIVIDER; state<=SCAN_SETTLE; cycles<=0;
            apply_wait<=0;
            COARSE_CODE<=0; FINE_SEED<=128; candidate<=0; bad_monitor<=0;
            best_error[0]<=16'hffff; best_error[1]<=16'hffff; best_error[2]<=16'hffff;
        end else begin
            apply_wait<=0;
            case(state)
                SCAN_SETTLE,LOW_SETTLE,HIGH_SETTLE: begin
                    if(!TUNING_APPLIED) cycles<=0;
                    else if(cycles==SETTLE_CYCLES[15:0]-16'd1) begin
                        start_count<=synchronized_count; cycles<=0;
                        case(state)
                            SCAN_SETTLE:state<=SCAN;
                            LOW_SETTLE:state<=LOW;
                            default:state<=HIGH;
                        endcase
                    end else cycles<=cycles+1'b1;
                end
                SCAN: begin
                    if(cycles==SCAN_CYCLES[15:0]-16'd1) begin
                        cycles<=0;
                        if(scan_error<best_error[0]) begin
                            best_error[2]<=best_error[1];best_band[2]<=best_band[1];
                            best_error[1]<=best_error[0];best_band[1]<=best_band[0];
                            best_error[0]<=scan_error;best_band[0]<=COARSE_CODE;
                        end else if(scan_error<best_error[1]) begin
                            best_error[2]<=best_error[1];best_band[2]<=best_band[1];
                            best_error[1]<=scan_error;best_band[1]<=COARSE_CODE;
                        end else if(scan_error<best_error[2]) begin
                            best_error[2]<=scan_error;best_band[2]<=COARSE_CODE;
                        end
                        if(COARSE_CODE==COARSE_BANDS[5:0]-6'd1) state<=PICK;
                        else begin COARSE_CODE<=COARSE_CODE+1'b1;state<=SCAN_SETTLE;end
                    end else cycles<=cycles+1'b1;
                end
                PICK: begin
                    COARSE_CODE<=best_band[candidate];FINE_SEED<=8;cycles<=0;
                    endpoint_window<=ENDPOINT_CYCLES[15:0];state<=LOW_SETTLE;
                end
                LOW,HIGH: begin
                    if(cycles==endpoint_window-1) begin
                        cycles<=0;
                        if(state==LOW) begin
                            low_count<=elapsed_edges;FINE_SEED<=247;state<=HIGH_SETTLE;
                        end else begin high_count<=elapsed_edges;state<=CHOOSE;end
                    end else cycles<=cycles+1'b1;
                end
                CHOOSE: begin
                    if(bracket) begin
                        FINE_INCREASING<=ascending;
                        seed_dividend<=seed_numerator;seed_divisor<=count_span;
                        seed_quotient<=0;seed_remainder<=0;seed_iterations<=32;
                        cycles<=0;state<=SEED_DIVIDE;
                    end else if(endpoint_window==ENDPOINT_CYCLES[15:0]) begin
                        endpoint_window<=ENDPOINT_CYCLES[15:0]*16'd2;FINE_SEED<=8;
                        cycles<=0;state<=LOW_SETTLE;
                    end else if(candidate<2 && {4'b0,candidate}<COARSE_BANDS[5:0]-6'd1) begin
                        candidate<=candidate+1'b1;state<=PICK;
                    end else state<=FAIL;
                end
                SEED_DIVIDE: begin
                    seed_dividend<={seed_dividend[30:0],1'b0};
                    seed_quotient<=seed_next_quotient;
                    seed_remainder<=seed_next_remainder[15:0];
                    seed_iterations<=seed_iterations-1'b1;
                    if(seed_iterations==1) begin
                        FINE_SEED<=interpolated_seed<8 ? 8 :
                            (interpolated_seed>247 ? 247 : interpolated_seed[7:0]);
                        cycles<=0;state<=LOAD;
                    end
                end
                LOAD: begin
                    if(!TUNING_APPLIED) cycles<=0;
                    else if(cycles==LOAD_CYCLES[15:0]-16'd1) begin
                        state<=TRACK;cycles<=0;start_count<=synchronized_count;
                    end else cycles<=cycles+1'b1;
                end
                TRACK: begin
                    if(cycles==MONITOR_CYCLES[15:0]-16'd1) begin
                        cycles<=0;start_count<=synchronized_count;bad_monitor<=monitor_bad;
                        if(monitor_bad && bad_monitor) state<=IDLE;
                    end else cycles<=cycles+1'b1;
                end
                FAIL: begin
                    // Retry from REFCLK even if the oscillator has stopped.
                    if(cycles==MONITOR_CYCLES[15:0]-16'd1) begin cycles<=0;state<=IDLE;end
                    else cycles<=cycles+1'b1;
                end
                default:state<=IDLE;
            endcase
            // A stopped DCO cannot acknowledge tuning. Bound that wait and
            // use the existing reference-clock retry path to recover.
            if(!TUNING_APPLIED && (state==SCAN_SETTLE || state==LOW_SETTLE ||
                                  state==HIGH_SETTLE || state==LOAD)) begin
                apply_wait<=apply_wait+1'b1;
                if(apply_wait==10'd511) begin state<=FAIL;cycles<=0;end
            end
        end
    end
endmodule
`default_nettype wire
