`timescale 1ns/1ps
module tb_calibration_reference_pause;
reg REFCLK=0, raw_clock=0, RESET_N=0, ref_run=1;
reg [7:0] seed=128;
wire OSC_RESET_N, CONFIG_READY, TRACKING, FAILED;
wire [7:0] DCO_CODE;
wire PLLOUT=raw_clock && OSC_RESET_N;
integer output_edges=0, reference_edges=0, saved_output, saved_reference;
always #20 if(ref_run) REFCLK=~REFCLK; else REFCLK=0;
always #1.25 raw_clock=~raw_clock;
always @(posedge PLLOUT) output_edges=output_edges+1;
always @(posedge REFCLK) reference_edges=reference_edges+1;
IntegerPLL_ProgrammedCore dut(
 .REFCLK(REFCLK),.PLLOUT(PLLOUT),.RESET_N(RESET_N),.PLL_ENABLE(1'b1),
 .STARTUP_COARSE(6'd20),.STARTUP_FINE(seed),.STARTUP_INCREASING(1'b1),
 .KI(8'd1),.KP(5'd3),.BBPD(2'b00),.OSC_RESET_N(OSC_RESET_N),
 .CONFIG_READY(CONFIG_READY),.TRACKING(TRACKING),.FAILED(FAILED),.DCO_CODE(DCO_CODE));
task check_pause;
 begin
  #40;
  saved_reference=reference_edges; saved_output=output_edges;
  #1000;
  if(reference_edges!=saved_reference || output_edges-saved_output<100)
   $fatal(1,"calibration clock isolation failed");
  if(OSC_RESET_N!==1'b1 || CONFIG_READY!==1'b0 || TRACKING!==1'b0 || FAILED!==1'b0 || DCO_CODE!==seed)
   $fatal(1,"paused startup did not retain the externally programmed seed");
  $display("CALIBRATION_PAUSE_OK seed=%0d edges=%0d",seed,output_edges-saved_output);
 end
endtask
initial begin
 #100; RESET_N=1;
 @(posedge OSC_RESET_N); ref_run=0;
 check_pause;
 ref_run=1;
 wait(TRACKING===1'b1); #1;
 if(DCO_CODE!==seed || FAILED!==1'b0) $fatal(1,"resume lost calibrated seed");
 $display("CALIBRATION_RESUME_OK");
 #200; RESET_N=0; seed=64;
 #100; RESET_N=1;
 @(posedge OSC_RESET_N); ref_run=0;
 check_pause;
 RESET_N=0; #1;
 if(OSC_RESET_N!==1'b0 || TRACKING!==1'b0 || CONFIG_READY!==1'b0)
  $fatal(1,"reset did not terminate calibration with reference stopped");
 seed=192; ref_run=1; #100; RESET_N=1;
 wait(TRACKING===1'b1); #1;
 if(DCO_CODE!==seed || FAILED!==1'b0) $fatal(1,"reprogram after calibration reset failed");
 $display("CALIBRATION_RESET_REPROGRAM_OK");
 $finish;
end
initial begin #9000;
 $display("DEBUG state=%0d failed=%b configured=%b ready=%b track=%b applied=%b fast=%b fine=%b corecode=%0d seed=%0d local=%h finecmd=%h dlfreset=%b fineclk=%b",dut.startup.state,FAILED,dut.config_ready,CONFIG_READY,TRACKING,dut.applied,dut.fast_applied,dut.fine_applied,dut.core_dco_code,dut.startup_seed,dut.local_command,dut.fine_command,dut.core.dlf_reset_n,dut.CLKDIV_RETIMED);
end
initial begin #10000; $fatal(1,"calibration protocol timeout"); end
endmodule
