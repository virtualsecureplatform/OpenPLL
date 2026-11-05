#!/usr/bin/env python3
"""Check the VPI bridge against exact Fraction timing and the frozen RTL.

All frequencies here are deliberately synthetic. Passing proves a scheduler
component, not a physical DCO/interface model or any PLL release case.
"""
import argparse
import csv
from datetime import datetime,timezone
from fractions import Fraction
import json
from pathlib import Path
import subprocess

from run_dco_qualification import ROOT,sha,save
from prepare_functional_matrix import FROZEN,FILES

TABLE={(0,0):100000000000,(0,1):200000000000,(0,2):333123456789,
       (1,0):400000000000,(1,1):250000000000,(47,255):1000000000000}


def ceil(value):
    return -(-value.numerator//value.denominator)


def oracle(actions,table,end):
    """Integrate continuous cycles; only observing edges rounds to1ps ticks."""
    state=dict(reset_n=0,coarse=0,fine=0)
    phase=Fraction(0);last=0;level=1;result=[]
    for time,changes in actions+[(end,{})]:
        if state['reset_n']:
            frequency=table[state['coarse'],state['fine']]
            finish=phase+Fraction((time-last)*frequency,10**15)
            crossing=(2*phase).__floor__()+1
            while Fraction(crossing,2)<=finish:
                when=Fraction(last)+(Fraction(crossing,2)-phase)*10**15/frequency
                level=1-level
                result.append((ceil(when),level))
                crossing+=1
            phase=finish
        state.update(changes)
        if not state['reset_n']:
            phase=Fraction(0);level=1
        last=time
    return result


def bench(actions,end,precision='1ps',fine_width=8):
    statements=[];last=0
    for time,changes in actions:
        assignments=[]
        for key,value in changes.items():
            width={'coarse':6,'fine':fine_width,'reset_n':1}[key]
            assignments.append(f"{key}={width}'b"+('x'*width if value=='x' else format(value,f'0{width}b'))+';')
        statements.append(f'#{time-last} '+''.join(assignments));last=time
    return f'''`timescale 1ps/{precision}
module bridge_case;
reg clock=1,reset_n=0;
reg [5:0] coarse=0;
reg [{fine_width-1}:0] fine=0;
initial begin
 $pll400_phase_clock(clock,coarse,fine,reset_n);
 {chr(10).join(statements)}
 #{end-last} $display("BENCH_END");
 $finish;
end
endmodule
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();out=a.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).resolve().parent
    source=here/'phase_clock_vpi.cpp'
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),source,here/'phase_clock.h',
        here/'prepare_functional_matrix.py',ROOT/'verification/timing450/IntegerPLL_ReleaseHarness.v',
        *[FROZEN/name for name in FILES],Path('/usr/bin/iverilog'),Path('/usr/bin/vvp'),Path('/usr/bin/iverilog-vpi')]}
    with (out/'vpi_compile.log').open('x') as log:
        subprocess.run(['/usr/bin/iverilog-vpi',str(source)],cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=43200)
    plugin=out/'phase_clock_vpi.vpi';pins[str(plugin)]=sha(plugin)
    standard=''.join(f'{coarse} {fine} {frequency}\n' for (coarse,fine),frequency in sorted(TABLE.items()))
    records={}

    def run(name,text,table=standard,top='bridge_case',rtl=False):
        directory=out/name;directory.mkdir()
        verilog=directory/'bench.v';verilog.write_text(text)
        model=directory/'synthetic.table';model.write_text(table)
        binary=directory/'bench.vvp';trace=directory/'trace.csv'
        argv=['/usr/bin/iverilog','-g2012','-s',top,'-o',str(binary)]
        if rtl:
            argv += [str(FROZEN/file) for file in FILES]+[str(ROOT/'verification/timing450/IntegerPLL_ReleaseHarness.v')]
        argv += [str(verilog)]
        with (directory/'compile.log').open('x') as log:
            subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=43200)
        with (directory/'run.log').open('x') as log:
            result=subprocess.run(['/usr/bin/vvp','-M',str(out),'-m','phase_clock_vpi',str(binary),
                '+phase400_table='+str(model),'+phase400_trace='+str(trace)],
                stdout=log,stderr=subprocess.STDOUT,timeout=43200)
        log=(directory/'run.log').read_text()
        paths=[verilog,model,binary,directory/'compile.log',directory/'run.log']
        if trace.exists():paths.append(trace)
        record=dict(returncode=result.returncode,error='PLL400_PHASE_ERROR:' in log,
                    bench_end='BENCH_END' in log,sha256={str(p):sha(p) for p in paths})
        return record,trace,log

    scenarios={
      'fixed400':([(1000,dict(reset_n=1,coarse=1))],500000),
      'midcycle_fine_and_coarse_changes':([(1000,dict(reset_n=1)),(3000,dict(fine=1)),
          (4800,dict(fine=2)),(17500,dict(coarse=1,fine=0)),(25000,dict(fine=1)),
          (38123,dict(coarse=47,fine=255))],100000),
      'coincident_tuning_edge':([(1000,dict(reset_n=1,coarse=1)),(2250,dict(fine=1))],100000),
      'tuning_one_tick_before_edge':([(1000,dict(reset_n=1,coarse=1)),(2249,dict(fine=1))],100000),
      'tuning_one_tick_after_edge':([(1000,dict(reset_n=1,coarse=1)),(2251,dict(fine=1))],100000),
      'reset_and_uncovered_code_while_stopped':([(1000,dict(reset_n=1)),(7300,dict(reset_n=0)),
          (8000,dict(fine=254)),(10000,dict(fine=1,reset_n=1))],100000),
    }
    for name,(actions,end) in scenarios.items():
        record,trace,log=run(name,bench(actions,end))
        assert record['returncode']==0 and not record['error'] and record['bench_end'],log
        rows=list(csv.DictReader(trace.open()))
        actual=[(int(row['time_ps']),int(row['level'])) for row in rows if row['event']=='EDGE']
        expected=oracle(actions,TABLE,end)
        assert actual==expected,(name,actual[:15],expected[:15])
        assert all(a[0]<b[0] for a,b in zip(actual,actual[1:]))
        record.update(passed=True,independent_fraction_edge_checks=len(expected),synthetic=True)
        records[name]=record

    # Long non-integer period: a rounded half-period implementation accumulates
    # error here. The correct bridge retains all sub-tick phase between edges.
    actions=[(1000,dict(reset_n=1))];end=200000000
    long_table=dict(TABLE);long_table[0,0]=100000534931
    table=''.join(f'{c} {f} {v}\n' for (c,f),v in sorted(long_table.items()))
    record,trace,log=run('long_fractional_period',bench(actions,end),table)
    assert record['returncode']==0 and not record['error'] and record['bench_end'],log
    actual=[(int(row['time_ps']),int(row['level'])) for row in csv.DictReader(trace.open()) if row['event']=='EDGE']
    expected=oracle(actions,long_table,end)
    assert actual==expected and len(actual)>39000
    naive=[1000+(i+1)*5000 for i in range(len(actual))]
    assert max(abs(t-naive[i]) for i,(t,_) in enumerate(actual))>1000
    record.update(passed=True,independent_fraction_edge_checks=len(expected),synthetic=True,
                  rounded_halfperiod_negative_control_rejected=True)
    records['long_fractional_period']=record

    bad_cases={
      'uncovered_lookup':(bench([(1000,dict(reset_n=1,fine=1))],10000),'0 0 100000000000\n0 2 200000000000\n','MODEL_LOOKUP_MISSING'),
      'unknown_control':(bench([(1000,dict(reset_n=1)),(2000,dict(fine='x'))],10000),standard,'CONTROL_XZ'),
      'duplicate_lookup':(bench([],10000),standard+'0 0 100000000000\n','MODEL_TABLE_INVALID'),
      'zero_frequency':(bench([],10000),'0 0 0\n','MODEL_TABLE_INVALID'),
      'invalid_code':(bench([],10000),'0 256 100000000000\n','MODEL_TABLE_INVALID'),
      'incomplete_model_row':(bench([],10000),'0 0\n','MODEL_TABLE_INVALID'),
      'wrong_time_precision':(bench([],10000,precision='100fs'),standard,'REQUIRES_1PS_PRECISION'),
      'wrong_argument_width':(bench([],10000,fine_width=7),standard,'CLOCK_ARGUMENT_WIDTHS_MUST_BE_1_6_8_1'),
    }
    for name,(text,table,reason) in bad_cases.items():
        record,trace,log=run(name,text,table)
        assert record['returncode']!=0 and record['error'] and not record['bench_end'] and reason in log,log
        record.update(passed=True,expected_error=reason,negative_control=True,synthetic=True)
        records[name]=record

    frozen='''`timescale 1ns/1ps
module frozen_bridge;
reg refclk=0,pllout=1,reset_n=1;
wire[5:0] coarse;wire[7:0] fine;
wire tracking,busy,failed,bbpd_reset_n;
always #20 refclk=~refclk;
IntegerPLL_ReleaseHarness dut(.REFCLK(refclk),.PLLOUT(pllout),.RESET_N(reset_n),
 .PLL_ENABLE(1'b0),.MODE_DIVIDER(5'd16),.BBPD(2'b00),.KI(8'd4),.KP(5'd0),
 .TRACKING(tracking),.CONFIG_BUSY(busy),.FAILED(failed),.BBPD_RESET_N(bbpd_reset_n),
 .CLKDIV_RETIMED(),.COARSE_CODE(coarse),.DCO_CODE(fine),.DLF_CODE());
initial begin
 // The oscillator is stopped in reset. Deliver an actual asynchronous reset
 // edge after event controls are installed; do not depend on a free clock
 // edge or on declaration initialization waking Verilog always blocks.
 #0 reset_n=0;
 $pll400_phase_clock(pllout,coarse,fine,reset_n);
 #10;
 if(tracking!==0 || busy!==0 || bbpd_reset_n!==0) $fatal(1,"reset boundary active");
 #30 reset_n=1;
 #500;
 if(tracking!==0 || busy!==0 || failed!==0 || bbpd_reset_n!==0) $fatal(1,"disabled boundary active");
 $display("BENCH_END frozen RTL disabled/reset integration only");$finish;
end
endmodule
'''
    # Full synthetic grid is only an integration fixture. No measured table is
    # filled in, extrapolated or promoted to obtain a passing physical result.
    grid=''.join(f'{coarse} {fine} {100000000000+fine*100000000}\n' for coarse in range(48) for fine in range(256))
    record,trace,log=run('frozen_candidate_bridge',frozen,grid,top='frozen_bridge',rtl=True)
    assert record['returncode']==0 and not record['error'] and record['bench_end'],log
    assert any(row['event']=='EDGE' for row in csv.DictReader(trace.open()))
    record.update(passed=True,synthetic=True,exact_frozen_rtl_disabled_reset_integration=True)
    records['frozen_candidate_bridge']=record
    for path,digest in pins.items():assert sha(path)==digest,path
    report=dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=len(records),
        passed=sum(r['passed'] for r in records.values()),records=records,sha256=pins,
        independent_fraction_edge_checks=sum(r.get('independent_fraction_edge_checks',0) for r in records.values()),
        no_interpolation_or_extrapolation=True,synthetic_component_checks_only=True,
        whole_pll_qualification_cases_passed=0,calibration_model_qualified=False,
        interface_model_qualified=False,release_qualified=False,
        limitations=['Ideal50percent-duty deterministic phase kernel; no physical startup, duty, settling, noise/jitter or supply effects.',
                     'No BBPD/receiver dynamic model or acquisition/lock qualification.',
                     'A future qualification runner must require independently qualified operating-point/model identities and reject any uncovered lookup.'])
    save(out/'assessment.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['records','sha256','limitations']}))


if __name__=='__main__':
    main()
