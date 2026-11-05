`timescale 1ns/1ps
// Physical clock boundary and measured phase challenge; actual controller RTL is unchanged.
module tb_programmed400_closed_loop;
    wire refclk;
    reg pllout=1, reset_n=1, enabled=0;
    reg [5:0] coarse=1;
    reg [7:0] seed=128, ki=4;
    reg [4:0] kp=0;
    reg polarity=1;
    wire osc_reset_n, ready, tracking, failed, divided, bbpd_reset_n;
    wire [1:0] bbpd;
    wire ref_at_detector, divided_physical, feedback_at_detector;
    Prototype400ClockTiming clock_boundary(
        .REFCLK(refclk),.DIVIDED_RTL(divided),.RESET_N(osc_reset_n),
        .REF_AT_DETECTOR(ref_at_detector),.DIVIDED_PHYSICAL(divided_physical),
        .FEEDBACK_AT_DETECTOR(feedback_at_detector));
    wire [7:0] fine;
    integer phase_ns, scenario, programmed_coarse, programmed_seed, selected_ki, selected_kp;
    integer selected_polarity, edge_file, segment_file;
    reg [2047:0] edge_path, segment_path;
    realtime enabled_at;
    Prototype400ReferencePhase reference_source(
        .TRACKING(tracking),.FEEDBACK_PHYSICAL(divided_physical),
        .PHASE_NS(phase_ns),.REFCLK(refclk));
    IntegerPLL_ProgrammedCore dut (
        .REFCLK(refclk),.PLLOUT(pllout),.RESET_N(reset_n),.PLL_ENABLE(enabled),
        .STARTUP_COARSE(coarse),.STARTUP_FINE(seed),.STARTUP_INCREASING(polarity),
        .KI(ki),.KP(kp),.BBPD(bbpd),.OSC_RESET_N(osc_reset_n),.CONFIG_READY(ready),
        .TRACKING(tracking),.CONFIG_BUSY(),.FAILED(failed),
        .CLKDIV_RETIMED(divided),.BBPD_RESET_N(bbpd_reset_n),
        .COARSE_CODE(),.DCO_CODE(fine),.DLF_CODE(),.COARSETHERMAL_CODE(),.DCO_THERM());
    Prototype400DetectorModel detector(
        .REFCLK(ref_at_detector),.FEEDBACKCLK(feedback_at_detector),.RESET_N(bbpd_reset_n),.BBPD(bbpd));
    always @(posedge refclk)
        if(edge_file) $fdisplay(edge_file,"REF,%.9f,%0d,%0d",$realtime,fine,bbpd);
    always @(posedge pllout)
        if(edge_file) $fdisplay(edge_file,"OUT,%.9f,%0d,%0d",$realtime,fine,bbpd);
    always @(posedge divided_physical)
        if(edge_file) $fdisplay(edge_file,"DIV,%.9f,%0d,%0d",$realtime,fine,bbpd);
    task observe_segment;
        input integer index;
        begin
            enabled_at=$realtime; enabled=1;
            #220000;
            if(failed || !tracking) $fatal(1,"startup failed or tracking withdrawn");
            $fdisplay(segment_file,"%0d,%.9f,%.9f",index,enabled_at,$realtime);
        end
    endtask
    initial begin
        if(!$value$plusargs("phase_ns=%d",phase_ns) ||
           !$value$plusargs("scenario=%d",scenario) ||
           !$value$plusargs("coarse=%d",programmed_coarse) ||
           !$value$plusargs("seed=%d",programmed_seed) ||
           !$value$plusargs("ki=%d",selected_ki) ||
           !$value$plusargs("kp=%d",selected_kp) ||
           !$value$plusargs("polarity=%d",selected_polarity) ||
           !$value$plusargs("edge_trace=%s",edge_path) ||
           !$value$plusargs("segment_trace=%s",segment_path)) $fatal(1,"missing explicit case input");
        if(phase_ns<0 || phase_ns>=40 || scenario<0 || scenario>2 ||
           programmed_coarse<0 || programmed_coarse>47 || programmed_seed<8 || programmed_seed>247 ||
           selected_ki<1 || selected_ki>255 || selected_kp<0 || selected_kp>31 ||
           selected_polarity<0 || selected_polarity>1) $fatal(1,"invalid case input");
        coarse=programmed_coarse;seed=programmed_seed;
        ki=selected_ki;kp=selected_kp;polarity=selected_polarity;
        edge_file=$fopen(edge_path,"w");segment_file=$fopen(segment_path,"w");
        if(!edge_file || !segment_file) $fatal(1,"trace open failed");
        $fdisplay(edge_file,"event,time_ns,code,bbpd");
        $fdisplay(segment_file,"segment,enabled_ns,stop_ns");
        #1 reset_n=0;
        $pll400_phase_clock(pllout,dut.COARSE_CODE,fine,osc_reset_n);
        #10 reset_n=1;
        #90;observe_segment(0);
        if(scenario==1) begin
            enabled=0;#1000;
            if(tracking || fine!==seed) $fatal(1,"open-loop restore failed");
            observe_segment(1);
        end
        if(scenario==2) begin
            #3.125 reset_n=0;#10;
            if(tracking || osc_reset_n) $fatal(1,"asynchronous reset failed");
            reset_n=1;observe_segment(1);
        end
        // Actual reference guard edges must extend past the observation horizon.
        #81;
        $fclose(edge_file);$fclose(segment_file);
        $display("PROGRAMMED400_LOOP_END scenario=%0d",scenario);
        $finish;
    end
    initial begin #500000;$fatal(1,"closed-loop driver timeout");end
endmodule
