"""Prove constant-ratio countdown divider output against an independent phase counter."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge import execute

YOSYS='/nix/store/4bmfi4470w0i3ixcaidfki18d3fyqvva-yosys-with-plugins-0.62/bin/yosys'


def run(output):
    source=ROOT/'rtl/prototype400/IntegerPLL_MMD_Retimer.v'
    output.mkdir(parents=True,exist_ok=False)
    harness=output/'harness.v'
    harness.write_text('''module fixed_divider_proof(input clk,input reset_n,output divided,output reference);
 IntegerPLL_MMD_Retimer #(.RATIO_WIDTH(5),.REGISTER_CONFIG(0),.COUNTDOWN(1),.CONFIG_PIPELINE(0)) dut(.DIV_IN(clk),.RESET_N(reset_n),.CLK_DIV_RATIO(5'd16),.CLKDIV_RETIMED(divided));
 reg [3:0] phase;
 reg expected;
 assign reference=expected;
 always @(posedge clk or negedge reset_n)
  if(!reset_n) begin phase<=0;expected<=0;end
  else begin phase<=phase+1'b1;expected<=(phase>=1 && phase<=8);end
 always @(posedge clk) assert(divided==reference);
endmodule
''')
    pins={str(p):sha(p) for p in (source,harness,Path(YOSYS),Path(__file__).resolve())}
    script=output/'proof.ys';script.write_text(f'read_verilog -formal {source} {harness}\nhierarchy -check -top fixed_divider_proof\nproc\nflatten\nasync2sync\nopt\ndffunmap\nopt\nsat -tempinduct -seq 20 -maxsteps 64 -set-init-zero -set-at 1 reset_n 0 -prove-asserts -verify -show-inputs -show-outputs\n')
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(1,4,deadline):execute([YOSYS,'-s',script],output/'proof.log',deadline,4)
    log=(output/'proof.log').read_text()
    if 'Induction step proven: SUCCESS!' not in log:raise ValueError('inductive proof missing')
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(script):sha(script),str(output/'proof.log'):sha(output/'proof.log')},
        inductive_constant_divider_output_equivalence=True,ratio=16,high_and_low_width_fast_cycles=8,
        arbitrary_reset_sequences=True,configuration='five_bit_countdown_direct_constant16',
        physical_timing_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args();run(a.output.resolve())
