`timescale 1ns/1ps
module tb_calibration_reference_pause;
reg REFCLK=0, raw_clock=0, RESET_N=1, ref_run=1;
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
 #1; RESET_N=0;
 repeat(3) @(posedge REFCLK); @(negedge REFCLK); #1; RESET_N=1;
 repeat(5) @(posedge REFCLK); @(negedge REFCLK); ref_run=0;
 check_pause;
 ref_run=1;
 wait(TRACKING===1'b1); #1;
 if(DCO_CODE!==seed || FAILED!==1'b0) $fatal(1,"resume lost calibrated seed");
 $display("CALIBRATION_RESUME_OK");
 #200; RESET_N=0; seed=64;
 repeat(3) @(posedge REFCLK); @(negedge REFCLK); #1; RESET_N=1;
 repeat(5) @(posedge REFCLK); @(negedge REFCLK); ref_run=0;
 check_pause;
 RESET_N=0; #1;
 if(OSC_RESET_N!==1'b0 || TRACKING!==1'b0 || CONFIG_READY!==1'b0)
  $fatal(1,"reset did not terminate calibration with reference stopped");
 seed=192; ref_run=1; repeat(3) @(posedge REFCLK); @(negedge REFCLK); #1; RESET_N=1;
 wait(TRACKING===1'b1); #1;
 if(DCO_CODE!==seed || FAILED!==1'b0) $fatal(1,"reprogram after calibration reset failed");
 $display("CALIBRATION_RESET_REPROGRAM_OK");
 $finish;
end
initial begin #10000; $fatal(1,"calibration protocol timeout"); end
endmodule
