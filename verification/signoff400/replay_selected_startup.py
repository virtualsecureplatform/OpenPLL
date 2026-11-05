"""Replay observed native input transitions through the candidate startup RTL.

PLLOUT is externally replayed, not a closed-loop oscillator model. BBPD is held
zero for this startup-only diagnostic. Comparisons do not qualify physical timing.
"""
import argparse,csv,json,subprocess,time
from pathlib import Path
from common_v3 import ROOT,source_pins,sha,save,verify


def run(trace,output):
    output.mkdir(parents=True,exist_ok=False);pins=source_pins();pins[str(trace)]=sha(trace)
    scalar={'refclk':'refclk','pllout':'pllout','reset_n':'reset_n','pll_enable':'enabled','startup_increasing':'polarity'}
    buses={'startup_coarse':('coarse',6),'startup_fine':('seed',8),'ki':('ki',8),'kp':('kp',5)}
    lines=[];last={};tick=0;end=None;native={}
    with trace.open() as f:
        for row in csv.DictReader(f):
            t=round(float(row['time'])*1e12);values={v:int(float(row[f'v({k})'])>=.9) for k,v in scalar.items()}
            for key,(name,n) in buses.items():values[name]=sum(int(float(row[f'v({key}[{i}])'])>=.9)<<i for i in range(n))
            changed={k:v for k,v in values.items() if last.get(k)!=v}
            if changed:
                lines.append(f'#{t-tick}; '+' '.join(f'{k}={v};' for k,v in changed.items()));tick=t;last=values
            end=t;native=row
    if end!=260000:raise ValueError('complete 260ns selected startup trace required')
    body='\n'.join(lines)+f'\n#{end-tick+1};\n$fdisplay(fd,"%d,%d,%d,%d,%d,%d,%d",ready,busy,tracking,failed,observed_coarse,fine,dut.startup.state);$fclose(fd);$finish;'
    bench='''`timescale 1ps/1ps
module replay;
reg refclk=0,pllout=0,reset_n=1,enabled=0,polarity=0;
reg [5:0] coarse=0; reg [7:0] seed=0,ki=0; reg [4:0] kp=0;
wire ready,busy,tracking,failed;wire [5:0] observed_coarse;wire [7:0] fine;
integer fd;
IntegerPLL_ProgrammedCore dut(.REFCLK(refclk),.PLLOUT(pllout),.RESET_N(reset_n),.PLL_ENABLE(enabled),.STARTUP_COARSE(coarse),.STARTUP_FINE(seed),.STARTUP_INCREASING(polarity),.KI(ki),.KP(kp),.BBPD(2'b00),.CONFIG_READY(ready),.CONFIG_BUSY(busy),.TRACKING(tracking),.FAILED(failed),.COARSE_CODE(observed_coarse),.DCO_CODE(fine));
initial begin fd=$fopen("final.csv","w");
'''+body+'\nend\nendmodule\n'
    (output/'bench.v').write_text(bench);rtl=[p for p in source_pins() if p.endswith('.v') and not p.endswith('IntegerPLL_400MHz_PrototypeTop.v')]
    start=time.monotonic()
    with (output/'run.log').open('w') as log:
        subprocess.run(['/usr/bin/iverilog','-g2012','-s','replay','-o',output/'replay.vvp',*rtl,output/'bench.v'],cwd=output,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
        subprocess.run(['/usr/bin/vvp',output/'replay.vvp'],cwd=output,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
    a=[int(v.strip()) for v in (output/'final.csv').read_text().strip().split(',')];keys=['config_ready','config_busy','tracking','failed','coarse_code','dco_code','startup_state']
    measured={k:int(float(native[f'v({k})'])>=.9) for k in keys[:4]}
    for k,n in [('coarse_code',6),('dco_code',8)]:measured[k]=sum(int(float(native[f'v({k}[{i}])'])>=.9)<<i for i in range(n))
    observed=dict(zip(keys,a));verify(pins)
    report=dict(input_sha256=pins,elapsed_s=time.monotonic()-start,native_end=measured,rtl_end=observed,end_state_matches=all(observed[k]==v for k,v in measured.items()),diagnostic=True,bbpd_assumed_zero=True,clock_is_native_replay=True,lock_qualified=False,release_ready=False)
    save(output/'assessment.json',report);print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--trace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.trace.resolve(),a.output.resolve())
