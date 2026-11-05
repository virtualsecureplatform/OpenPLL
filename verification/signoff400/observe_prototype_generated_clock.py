"""Measure frozen RTL generated-clock edge spacing across startup regression; no analog/STA claim."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import time
from common_v3 import ROOT,PROFILE,RTL,save,sha,verify
from resources import identity,lease
from compiled_charge import execute

MONITOR=r'''
    integer observed_dco_cycle=0;
    integer observed_clock_fd;
    always @(posedge pllout) observed_dco_cycle=observed_dco_cycle+1;
    initial begin
        observed_clock_fd=$fopen("generated_clock.csv","w");
        $fwrite(observed_clock_fd,"event,time_ns,dco_cycle,level,reset_n,oscillator_reset_n,fast_reset_n,tracking,phase\n");
    end
    always @(divided) if(observed_clock_fd)
        $fwrite(observed_clock_fd,"DIV,%0.3f,%0d,%b,%b,%b,%b,%b,%0d\n",$realtime,observed_dco_cycle,divided,reset_n,oscillator_reset_n,dut.core.fast_reset_n,tracking,phase_index);
    always @(reset_n or oscillator_reset_n or dut.core.fast_reset_n) if(observed_clock_fd)
        $fwrite(observed_clock_fd,"RESET,%0.3f,%0d,%b,%b,%b,%b,%b,%0d\n",$realtime,observed_dco_cycle,divided,reset_n,oscillator_reset_n,dut.core.fast_reset_n,tracking,phase_index);
'''


def analyze(rows):
    epoch=0;previous=None;rise=None;periods=[];widths=[];ordinary_edges=0
    for row in rows:
        enabled=all(row[k]=='1' for k in ('reset_n','oscillator_reset_n','fast_reset_n'))
        if not enabled:
            epoch+=1;previous=None;rise=None;continue
        if row['event']!='DIV':continue
        if row['level'] not in ('0','1'):raise ValueError('unknown active generated clock')
        current=dict(cycle=int(row['dco_cycle']),level=int(row['level']),tracking=row['tracking']=='1',phase=int(row['phase']))
        ordinary_edges+=1
        if previous:
            width=current['cycle']-previous['cycle']
            if width<=0 or current['level']==previous['level']:raise ValueError('invalid synchronous generated-clock transition')
            widths.append(dict(cycles=width,level=previous['level'],tracking_at_both_edges=current['tracking'] and previous['tracking'],phase=current['phase']))
        if current['level']==1:
            if rise:
                period=current['cycle']-rise['cycle']
                if period<=0:raise ValueError('invalid generated-clock period')
                periods.append(dict(cycles=period,tracking_at_both_edges=current['tracking'] and rise['tracking'],phase=current['phase']))
            rise=current
        previous=current
    if not periods or not widths:raise ValueError('no measured generated-clock intervals')
    return dict(ordinary_edges=ordinary_edges,periods=periods,pulse_widths=widths,
        observed_minimum_period_dco_cycles=min(x['cycles'] for x in periods),
        observed_minimum_high_dco_cycles=min(x['cycles'] for x in widths if x['level']==1),
        observed_minimum_low_dco_cycles=min(x['cycles'] for x in widths if x['level']==0),
        tracking_periods_dco_cycles=sorted({x['cycles'] for x in periods if x['tracking_at_both_edges']}),
        exhaustive_clock_bound_proved=False,analog_pulse_width_or_STA_qualified=False)


def run(output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+300
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4))
    bench=ROOT/'tb/tb_programmed400.v';text=bench.read_text()
    if text.count('endmodule')!=1:raise ValueError('single startup bench required')
    instrumented=output/'clock_observer.v';instrumented.write_text(text.replace('endmodule',MONITOR+'\nendmodule'))
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    paths=[PROFILE,*RTL,bench,instrumented,image,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    binary=output/'clock_observer.vvp';prefix=['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',output,image]
    with lease(1,4,deadline):
        execute([*prefix,'/usr/bin/iverilog','-g2012','-s','tb_programmed400','-o',binary,*RTL,instrumented],output/'compile.log',deadline,4)
        execute([*prefix,'/usr/bin/vvp',binary],output/'native.log',deadline,4)
    if 'PASS' not in (output/'native.log').read_text():raise ValueError('startup regression did not pass')
    trace=output/'generated_clock.csv';rows=list(csv.DictReader(trace.open()));result=analyze(rows)
    detail=output/'clock_metrics.json';save(detail,result);verify(pins)
    artifacts={str(p):sha(p) for p in (binary,trace,detail,output/'compile.log',output/'native.log')}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
        observed_minimum_period_dco_cycles=result['observed_minimum_period_dco_cycles'],observed_minimum_high_dco_cycles=result['observed_minimum_high_dco_cycles'],observed_minimum_low_dco_cycles=result['observed_minimum_low_dco_cycles'],
        tracking_periods_dco_cycles=result['tracking_periods_dco_cycles'],generated_clock='CLKDIV_RETIMED',
        exhaustive_clock_bound_proved=False,actual_startup_frequency_bound_qualified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    print({k:v for k,v in result.items() if k not in ('periods','pulse_widths')})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
