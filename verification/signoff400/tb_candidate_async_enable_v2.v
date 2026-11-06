`timescale 1ns/1ps
module bench;
reg refclk=0,pllout=0,reset_n=1,enable=0,osc_run=1;
wire osc_reset,ready,tracking,failed;
wire [7:0] code;
integer phase_ps=1,mode=0;
reg [1:0] expected_pipe=0;
always #20 refclk=~refclk;
always #1.25 if(osc_reset && osc_run) pllout=~pllout;else pllout=0;
IntegerPLL_ProgrammedCore dut(.REFCLK(refclk),.PLLOUT(pllout),.RESET_N(reset_n),.PLL_ENABLE(enable),.STARTUP_COARSE(6'd20),.STARTUP_FINE(8'd160),.STARTUP_INCREASING(1'b1),.BBPD(2'b00),.KI(8'd4),.KP(5'd0),.OSC_RESET_N(osc_reset),.CONFIG_READY(ready),.TRACKING(tracking),.FAILED(failed),.DCO_CODE(code));
always @(posedge refclk or negedge dut.ref_reset_n) begin
 if(!dut.ref_reset_n) expected_pipe<=0;else expected_pipe<={expected_pipe[0],enable};
 #0.001;
 if(dut.enable_ref_pipe!==expected_pipe || dut.startup.PLL_ENABLE!==expected_pipe[1]) $fatal(1,"reference enable pipeline differs");
end
task automatic require_tracking;
 integer k,stable;
 begin
 k=0;stable=0;while(stable<200 && k<10000) begin
 #1;k=k+1;
 if(failed) $fatal(1,"unexpected sticky failure");
 if(tracking===1 && code===160) stable=stable+1;else stable=0;
 end
 if(stable<200 || failed || code!==160) $fatal(1,"failed tracking/restart code=%d ready=%b failed=%b",code,ready,failed);
 end
endtask
initial begin
 #1;reset_n=0;
 if(!$value$plusargs("PHASE_PS=%d",phase_ps)) phase_ps=1;
 if(!$value$plusargs("MODE=%d",mode)) mode=0;
 #63;reset_n=1;wait(ready===1);
 @(negedge refclk);#(phase_ps/1000.0);enable=1;
 require_tracking();
 @(negedge refclk);#(phase_ps/1000.0);enable=0;
 #0.001;if(tracking!==0 || code!==160) $fatal(1,"raw enable failed immediate withdrawal");
 if(mode==0) #120;
 if(mode==1) #3.001;
 if(mode==2) begin osc_run=0;#200;osc_run=1;end
 enable=1;require_tracking();
 #7.001;reset_n=0;#0.001;if(tracking!==0) $fatal(1,"reset failed withdrawal");
 #63;reset_n=1;require_tracking();
 $display("ASYNC_ENABLE_CANDIDATE_LOGIC_PASS phase_ps=%0d mode=%0d",phase_ps,mode);$finish;
end
initial begin #20000;$fatal(1,"candidate logic timeout");end
endmodule
