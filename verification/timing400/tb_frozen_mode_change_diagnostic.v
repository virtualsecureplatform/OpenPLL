// Synthetic directed-mode-change bring-up only; no physical-model qualification.
`timescale 1ns/1ps
module frozen_mode_change_diagnostic;
    reg refclk=0, pllout=1, reset_n=1, enabled=0;
    reg [4:0] divider=16;
    reg [1:0] bbpd=0;
    reg [7:0] gain_ki=4;
    reg [4:0] gain_kp=0;
    integer selected_ki, selected_kp;
    wire [5:0] coarse;
    wire [7:0] fine;
    wire [9:0] dlf;
    wire divided, detector_reset_n, tracking, busy, failed;
    integer selected_divider, next_divider, edges_file, state_file;
    reg [2047:0] edges_path, states_path;
    realtime last_ref=-20, phase_error;
    always #20 refclk=~refclk;
    IntegerPLL_ReleaseHarness dut(
        .REFCLK(refclk),.PLLOUT(pllout),.RESET_N(reset_n),.PLL_ENABLE(enabled),
        .MODE_DIVIDER(divider),.BBPD(bbpd),.KI(gain_ki),.KP(gain_kp),
        .CLKDIV_RETIMED(divided),.BBPD_RESET_N(detector_reset_n),
        .TRACKING(tracking),.CONFIG_BUSY(busy),.FAILED(failed),
        .COARSE_CODE(coarse),.DCO_CODE(fine),.DLF_CODE(dlf));
    always @(posedge refclk) begin
        last_ref=$realtime;
        if(edges_file) $fdisplay(edges_file,"REF,%.9f,%0d,%0d",$realtime,fine,bbpd);
    end
    always @(posedge pllout)
        if(edges_file) $fdisplay(edges_file,"OUT,%.9f,%0d,%0d",$realtime,fine,bbpd);
    always @(posedge divided) begin
        if(edges_file) $fdisplay(edges_file,"DIV,%.9f,%0d,%0d",$realtime,fine,bbpd);
        // Ideal deterministic phase decision at the actual feedback edge.
        // Pulse timing/aperture/storage are deliberately synthetic.
        phase_error=$realtime-last_ref;
        phase_error=phase_error-40.0*$floor((phase_error+20.0)/40.0);
        if(detector_reset_n === 1'b1) begin
            #0.2;
            if(phase_error>0.0) bbpd=2'b10;
            else if(phase_error<0.0) bbpd=2'b01;
            #0.2 bbpd=0;
        end
    end
    always @(coarse or fine or tracking or busy or failed or divider)
        if(state_file) $fdisplay(state_file,"%.9f,%0d,%0d,%0d,%0d,%0d,%0d",$realtime,divider,coarse,fine,tracking,busy,failed);
    initial begin
        if(!$value$plusargs("divider=%d",selected_divider)) $fatal(1,"missing divider");
        if(!(selected_divider==4 || selected_divider==10 || selected_divider==12 || selected_divider==16))
            $fatal(1,"unsupported divider");
        if(!$value$plusargs("next_divider=%d",next_divider)) $fatal(1,"missing next divider");
        if(!(next_divider==4 || next_divider==10 || next_divider==12 || next_divider==16) ||
            next_divider==selected_divider) $fatal(1,"unsupported directed change");
        if(!$value$plusargs("edge_trace=%s",edges_path) || !$value$plusargs("state_trace=%s",states_path))
            $fatal(1,"missing trace paths");
        edges_file=$fopen(edges_path,"w"); state_file=$fopen(states_path,"w");
        if(!edges_file || !state_file) $fatal(1,"trace open failed");
        $fdisplay(edges_file,"event,time_ns,code,bbpd");
        $fdisplay(state_file,"time_ns,divider,coarse,fine,tracking,busy,failed");
        divider=selected_divider;
        if(!$value$plusargs("gain_ki=%d",selected_ki) || !$value$plusargs("gain_kp=%d",selected_kp))
            $fatal(1,"explicit diagnostic gains required");
        if(selected_ki<1 || selected_ki>255 || selected_kp<0 || selected_kp>31)
            $fatal(1,"invalid diagnostic gains");
        gain_ki=selected_ki; gain_kp=selected_kp;
        // Explicit reset edge after observers are installed, including when
        // the phase driver has stopped the oscillator high.
        #0 reset_n=0;
        $pll400_phase_clock(pllout,coarse,fine,reset_n);
        #10 reset_n=1;
        #90 enabled=1;
        #220000;
        divider=next_divider;
        $display("SYNTHETIC_MODE_CHANGE time_ns=%.3f divider=%0d",$realtime,divider);
        #220000;
        $display("SYNTHETIC_MODE_CHANGE_END divider=%0d failed=%0d tracking=%0d",divider,failed,tracking);
        $fclose(edges_file); $fclose(state_file);
        $finish;
    end
endmodule
