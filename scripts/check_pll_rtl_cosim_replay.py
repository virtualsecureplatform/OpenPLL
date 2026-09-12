#!/usr/bin/env python3
"""Check every Verilator boundary evaluation against Icarus on the same RTL."""
import argparse
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('replay',type=Path)
p.add_argument('--seed',type=int,default=235)
p.add_argument('--ki',type=int,default=4)
p.add_argument('--kp',type=int,default=4)
p.add_argument('--ndiv',type=int,default=4)
p.add_argument('--coarse',type=int,default=17)
p.add_argument('--acquisition',action='store_true')
a=p.parse_args()
with a.replay.open() as stream:
    columns=len(stream.readline().split())
if columns not in (9,11): p.error('replay must have 9 legacy or 11 current columns')
if a.acquisition and columns!=11: p.error('acquisition requires a current replay')
out=a.replay.resolve().parent
bench=out/'replay.v'
bench.write_text('''`timescale 1ns/1ps
module replay;
reg PLLOUT, RESET_N, PLL_ENABLE, REFCLK=0;
reg [1:0] BBPD;
wire CLKDIV_RETIMED, BBPD_RESET_N, TRACKING;
wire [7:0] DCO_CODE;
wire [9:0] DLF_CODE;
wire [5:0] COARSE_CODE;
IntegerPLL_Cosim dut(.PLLOUT(PLLOUT),.RESET_N(RESET_N),.PLL_ENABLE(PLL_ENABLE),
 .REFCLK(REFCLK),.ACQUIRE(1'bACQUIRE_VALUE),.COARSE_CODE(COARSE_CODE),
 .BBPD(BBPD),.MODE_DIVIDER(5'dNDIV_VALUE),.COARSE_SEED(6'dCOARSE_VALUE),.SEED(8'dSEED_VALUE),.KI(8'dKI_VALUE),.KP(5'dKP_VALUE),
 .CLKDIV_RETIMED(CLKDIV_RETIMED),.BBPD_RESET_N(BBPD_RESET_N),
 .TRACKING(TRACKING),.DCO_CODE(DCO_CODE),.DLF_CODE(DLF_CODE));
integer fd, n, row=0;
integer osc,rst,en,pd,div_expected,reset_expected,track_expected,code_expected,dlf_expected;
integer ref_value,coarse_expected;
string path;
initial begin
 if (!$value$plusargs("REPLAY=%s",path)) $fatal(1,"Missing replay");
 fd=$fopen(path,"r"); if (!fd) $fatal(1,"Cannot open replay");
 while (!$feof(fd)) begin
  READ_ROW
  if(n!=COLUMN_COUNT) $fatal(1,"Malformed replay row");
  PLLOUT=osc; RESET_N=rst; PLL_ENABLE=en; BBPD=pd; REFCLK=ref_value;
  #0.001;
  // First row intentionally has no reset assertion yet; four-state RTL is X.
  if(row>0 && ({CLKDIV_RETIMED,BBPD_RESET_N,TRACKING,DCO_CODE,DLF_CODE} !==
     {div_expected[0],reset_expected[0],track_expected[0],code_expected[7:0],dlf_expected[9:0]}))
    $fatal(1,"Mismatch row=%0d actual=%0d,%0d,%0d,%0d,%0d expected=%0d,%0d,%0d,%0d,%0d",row,
     CLKDIV_RETIMED,BBPD_RESET_N,TRACKING,DCO_CODE,DLF_CODE,div_expected,reset_expected,track_expected,code_expected,dlf_expected);
  #0.001; row=row+1;
  if(row>1 && COARSE_CODE!==coarse_expected[5:0]) $fatal(1,"Coarse mismatch row=%0d",row);
 end
 $display("rtl_replay=pass evaluations=%0d",row); $finish;
end
endmodule
'''.replace('READ_ROW',
    'n=$fscanf(fd,"'+' '.join(['%d']*columns)+'\\n",osc,rst,en,pd,div_expected,reset_expected,track_expected,code_expected,dlf_expected'+
    (',ref_value,coarse_expected);' if columns==11 else f');ref_value=0;coarse_expected={a.coarse};'))
    .replace('COLUMN_COUNT',str(columns)).replace('ACQUIRE_VALUE',str(int(a.acquisition)))
    .replace('NDIV_VALUE',str(a.ndiv)).replace('COARSE_VALUE',str(a.coarse)).replace('SEED_VALUE',str(a.seed)).replace('KI_VALUE',str(a.ki)).replace('KP_VALUE',str(a.kp)))
rtl=['IntegerPLL_AcquiringCore','IntegerPLL_TuningHandoff','IntegerPLL_FrequencyAcquisition','IntegerPLL_25MHzModeController','IntegerPLL_25MHzModeConfig','IntegerPLL_DigitalCore','IntegerPLL_DLF','IntegerPLL_B2TH','IntegerPLL_MMD_Retimer','IntegerPLL_Divider']
subprocess.run(['iverilog','-g2012','-s','replay','-o',str(out/'replay.vvp'),str(bench),str(ROOT/'tb/IntegerPLL_Cosim.v')]+[str(ROOT/'rtl'/f'{name}.v') for name in rtl],check=True)
subprocess.run(['vvp',str(out/'replay.vvp'),f'+REPLAY={a.replay.resolve()}'],check=True)
