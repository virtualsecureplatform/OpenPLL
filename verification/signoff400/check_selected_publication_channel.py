"""Exercise alternating Q direction and cancellation across reset on a generated adapter."""
import argparse,json,subprocess
from pathlib import Path
from common_v3 import save,sha,verify


def run(packet,output):
    a=json.loads((packet/'assessment.json').read_text());verify(a['input_sha256']);verify(a['artifacts']);output.mkdir(parents=True,exist_ok=False)
    source=packet/'detector.v';bench=output/'bench.v'
    lines=['`timescale 1ns/1ps','module bench;reg raw=0,reset_n=0;wire up,dn;']
    for role in ['up','dn']:
        d=a['effective_publication_delay_ns'][role]
        lines += [f'Prototype400PublicationChannel #(.RISE_Q_NS({d["rise"]:.17g}),.FALL_Q_NS({d["fall"]:.17g})) {role}_dut(raw,reset_n,{role});',f'always @({role}) if($realtime>0.5) $display("EDGE {role} %.9f %b",$realtime,{role});']
    lines += ['initial begin #1;reset_n=1;#1;raw=1;#1;raw=0;#1;raw=1;#1;raw=0;#1;raw=1;#0.1;reset_n=0;#0.1;raw=0;#0.8;reset_n=1;#1;raw=1;#1;raw=0;#1;$display("CHANNEL_CHECK_END");$finish;end','endmodule']
    bench.write_text('\n'.join(lines)+'\n')
    with (output/'compile.log').open('x') as log:subprocess.run(['/usr/bin/iverilog','-g2012','-s','bench','-o',str(output/'bench.vvp'),str(source),str(bench)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=60)
    result=subprocess.run(['/usr/bin/vvp',str(output/'bench.vvp')],capture_output=True,text=True,check=True,timeout=60);(output/'run.log').write_text(result.stdout+result.stderr)
    if 'CHANNEL_CHECK_END' not in result.stdout:raise ValueError('incomplete check')
    records=[]
    for role in ['up','dn']:
        d=a['effective_publication_delay_ns'][role];expected=[(t+d[direction],value) for t,direction,value in [(2,'rise',1),(3,'rise',0),(4,'fall',1),(5,'fall',0),(8,'rise',1),(9,'rise',0)]]
        actual=[(float(x[2]),int(x[3])) for line in result.stdout.splitlines() if (x:=line.split())[:2]==['EDGE',role]]
        passed=len(actual)==len(expected) and all(abs(t-u)<=.000501 and v==w for (t,v),(u,w) in zip(actual,expected));records.append(dict(role=role,actual=actual,expected=expected,passed=passed))
    files=[packet/'assessment.json',source,bench,Path(__file__).resolve(),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]
    passed=all(x['passed'] for x in records);save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()},records=records,alternating_delay_and_reset_cancellation_pass=passed,physical_timing_qualified=False,release_ready=False))
    if not passed:raise ValueError('publication adapter behavior mismatch')
    print('alternating direction, pulse widths and reset cancellation pass for UP and DN')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['packet','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.packet.resolve(),a.output.resolve())
