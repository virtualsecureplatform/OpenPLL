// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_frequency_acquisition;
    reg refclk=0, dco=0, reset_n=0, enable=0;
    reg [4:0] divider=4;
    reg oscillator_running=1;
    reg force_rail=0;
    wire [5:0] coarse;
    wire [7:0] seed;
    wire run_fine,busy,failed,fine_increasing;
    real scale=1.0;
    real initial_phase=7.0;
    real started;
    reg [47:0] seen=0;
    integer mode;
    IntegerPLL_FrequencyAcquisition dut(
        .REFCLK(refclk),.PLLOUT(dco),.RESET_N(reset_n),.PLL_ENABLE(enable),
        .FEEDBACK_DIVIDER(divider),.FINE_CODE(force_rail ? 8'd255 : seed),.COARSE_CODE(coarse),.FINE_SEED(seed),
        .FINE_INCREASING(fine_increasing),
        .TUNING_APPLIED(1'b1),
        .DCO_RESET_N(reset_n),
        .RUN_FINE(run_fine),.BUSY(busy),.FAILED(failed));
    always #20 refclk=~refclk;
    function real mhz;
        input [5:0] band;
        input [7:0] code;
        begin
            case(band)
                17:mhz=102.0-code*4.0/255.0; // Reversed fine polarity.
                6:mhz=248.0+code*4.0/255.0;
                4:mhz=297.0+code*6.0/255.0;
                2:mhz=396.0+code*8.0/255.0;
                0:mhz=495.0+code*10.0/255.0;
                1:mhz=100.0; // Closest midpoint, but no usable tuning span.
                default:mhz=650.0+band*10.0+code*0.02;
            endcase
        end
    endfunction
    initial begin
        if($value$plusargs("PHASE_NS=%f",initial_phase)) begin end
        #(initial_phase);
        forever begin
            #(500.0/(mhz(coarse,seed)*scale));
            if(oscillator_running) dco=~dco;
        end
    end
    always @(posedge refclk) if(enable&&!run_fine) seen[coarse]<=1;
    task acquire;
        input [4:0] next_divider;
        input [5:0] expected_band;
        begin
            @(negedge refclk);divider=next_divider;seen=0;started=$realtime;
            // Mode changes must withdraw handoff even before the next REF edge.
            #1;
            if(run_fine) $fatal(1,"stale mode handoff");
            while(!run_fine && !failed) begin @(posedge refclk);#1;end
            if(failed || coarse!=expected_band || seed<8 || seed>247)
                $fatal(1,"bad acquisition divider=%0d coarse=%0d seed=%0d",divider,coarse,seed);
            if(fine_increasing!==(expected_band!=17)) $fatal(1,"wrong fine polarity");
            if(seen!==48'hffffffffffff) $fatal(1,"not all bands scanned");
            if($realtime-started>180000) $fatal(1,"acquisition budget exceeded");
            if((mhz(coarse,seed)>divider*25.0*1.01) || (mhz(coarse,seed)<divider*25.0*0.99))
                $fatal(1,"seed outside fine-loop capture neighborhood");
            $display("acquire divider=%0d coarse=%0d seed=%0d elapsed_ns=%0.3f",divider,coarse,seed,$realtime-started);
            #1000;
        end
    endtask
    initial begin
        #1;reset_n=0;#99;reset_n=1;enable=1;
        acquire(4,17);
        acquire(10,6);
        acquire(12,4);
        acquire(16,2);
        acquire(20,0);
        force_rail=1;
        wait(!run_fine);
        force_rail=0;
        while(!run_fine) begin @(posedge refclk);#1;end
        scale=0.8;
        started=$realtime;
        wait(!run_fine);
        if($realtime-started>62000) $fatal(1,"frequency loss not detected");
        // Disable and invalid mode must not falsely hand off.
        enable=0;#100;divider=3;enable=1;#1000;
        if(run_fine) $fatal(1,"invalid divider accepted");
        enable=0;scale=1;#100;
        divider=4;enable=1;
        while(!run_fine) begin @(posedge refclk);#1;end
        oscillator_running=0;
        wait(!run_fine);
        wait(failed);
        if(run_fine) $fatal(1,"stopped oscillator accepted");
        oscillator_running=1;
        while(!run_fine) begin @(posedge refclk);#1;end
        $display("frequency_acquisition=pass");$finish;
    end
    initial begin #2000000;$fatal(1,"watchdog timeout");end
endmodule
