#!/usr/bin/env python3
"""One-process extracted combinational propagation batch, never a timing library.

All sensitizing static side-input states are included. One PVT point and a
finite load/slew grid cannot qualify interpolation, numerical error, sequential
constraints, metal corners or complete nominal15PVT coverage.
"""
import argparse
import ast
from datetime import datetime, timezone
import itertools
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, REQUIREMENTS, sha, save
sys.path.insert(0,str(ROOT/'verification/timing450'))
from enforce_native_check_budget import process as native_process

SOURCE=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/cells'
PDK=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A')
XYCE=Path('/opt/xyce/bin/Xyce')
SUPPLIES={'VNB':'0','VPB':'VDD','VPWR':'VDD','VGND':'0'}


def truth(text,values):
    tree=ast.parse(text.replace('!','~'),mode='eval')
    def visit(node):
        if isinstance(node,ast.Expression):return visit(node.body)
        if isinstance(node,ast.Name):return values[node.id]
        if isinstance(node,ast.Constant) and node.value in (0,1):return int(node.value)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Invert):return 1-visit(node.operand)
        if isinstance(node,ast.BinOp):
            left,right=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.BitAnd):return left&right
            if isinstance(node.op,ast.BitOr):return left|right
            if isinstance(node.op,ast.BitXor):return left^right
        raise ValueError('unsupported Boolean expression: '+text)
    return visit(tree)


def expected(family,v):
    if family in ('buf','clkbuf'):return v['A']
    if family in ('inv','clkinv'):return 1-v['A']
    if family=='nand2':return 1-(v['A']&v['B'])
    if family=='nor2':return 1-(v['A']|v['B'])
    if family=='a21oi':return 1-((v['A1']&v['A2'])|v['B1'])
    if family=='o21ai':return 1-((v['A1']|v['A2'])&v['B1'])
    if family=='xor2':return v['A']^v['B']
    if family=='xnor2':return 1-(v['A']^v['B'])
    if family=='mux2':return v['A1'] if v['S'] else v['A0']
    if family=='maj3':return int(v['A']+v['B']+v['C']>=2)
    raise ValueError('unsupported family: '+family)


def crossings(times,values,threshold,rising):
    result=[]
    for ta,tb,a,b in zip(times,times[1:],values,values[1:]):
        if (a<threshold<=b if rising else b<threshold<=a):
            result.append(ta+(tb-ta)*(threshold-a)/(b-a))
    return result


def admit_one(out):
    # Single launch only, with two free slots and no preparing/waiting DCO
    # worker. Once Xyce is live the existing controller counts it as external.
    status_path=ROOT/'build/timing400/release_001/dco/status.json'
    status=json.loads(status_path.read_text())
    assert not any(v.get('state')=='waiting_for_native_slot' for v in status['stages'].values())
    engines={v['engine_pid'] for v in status['stages'].values()
             if v.get('state')=='running' and 'engine_pid' in v}
    native=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():continue
        found=native_process(int(entry.name),ROOT)
        if found:
            try:found['ppid']=int((entry/'stat').read_text().rsplit(')',1)[1].split()[1])
            except (OSError,ValueError):continue
            native.append(found)
    assert len(native)<=2,'requires two free native slots before the single launch'
    assert engines=={n['ppid'] for n in native if n['ppid'] in engines},'DCO engine is still preparing'
    save(out/'admission.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        native_before=native,running_dco_engines=sorted(engines),status_snapshot=status,
        single_native_launch=True,max_workspace_native_workers=4))


def main():
    started=time.monotonic()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--corner',required=True,choices=['tt','ff','ss','sf','fs'])
    parser.add_argument('--temperature-c',required=True,type=int,choices=[-40,27,125])
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args();route=args.route.resolve();out=args.output.resolve()
    receipt=verify(route/'assessment.json')
    out.mkdir(parents=True,exist_ok=False)
    index_path=ROOT/'build/timing400/release_001/hs_cell_model_index_001/assessment.json'
    index=json.loads(index_path.read_text())['models']
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),REQUIREMENTS,index_path,route/'assessment.json',XYCE]}
    spec=json.loads(REQUIREMENTS.read_text());assert spec['voltages']==[1.8]
    provenance_path=ROOT/'build/modern_25mhz/nominal_release_dco_path_001/screen/provenance.json'
    provenance=json.loads(provenance_path.read_text());pins[str(provenance_path)]=sha(provenance_path)
    for path,digest in provenance['files'].items():
        if str(PDK) in path and Path(path).suffix in ('.spice','.pm3','.mod','.lib'):
            assert sha(path)==digest,path;pins[path]=digest
    definitions=[];cases=[];sequential=[];truth_rows=0
    for master in sorted(receipt['master_counts']):
        family=master.split('__')[1].rsplit('_',1)[0]
        if family in ('dfrtp','dfstp'):sequential.append(master);continue
        if master not in index:continue
        source=SOURCE/family/(master+'__tt_025C_1v80_ccsnoise.lib.json')
        if not source.exists():source=SOURCE/family/(master+'__tt_025C_1v80.lib.json')
        data=json.loads(source.read_text());pins[str(source)]=sha(source)
        cell_pins={name[4:]:v for name,v in data.items() if name.startswith('pin,') and isinstance(v,dict)}
        inputs=sorted(n for n,v in cell_pins.items() if v.get('direction')=='input')
        outputs=[n for n,v in cell_pins.items() if v.get('direction')=='output']
        assert len(outputs)==1 and 1<=len(inputs)<=3
        output=outputs[0];function=cell_pins[output]['function']
        cap=float(cell_pins[output]['max_capacitance']);assert cap>0
        for bits in itertools.product((0,1),repeat=len(inputs)):
            values=dict(zip(inputs,bits));assert truth(function,values)==expected(family,values)
            truth_rows+=1
        model=Path(index[master]['model']);assert sha(model)==index[master]['model_sha256']
        pins[str(model)]=sha(model);definitions.append(model)
        ports=index[master]['ports'];assert set(ports)==set(inputs)|{output}|set(SUPPLIES)
        for changing in inputs:
            others=[p for p in inputs if p!=changing]
            for bits in itertools.product((0,1),repeat=len(others)):
                side=dict(zip(others,bits))
                low=truth(function,{**side,changing:0});high=truth(function,{**side,changing:1})
                if low==high:continue
                for ramp_ps,load_pf in itertools.product((20,200,1000/0.6),(0,cap/4,cap)):
                    cases.append(dict(master=master,input=changing,output=output,side_inputs=side,
                        inverted=low>high,full_ramp_ps=ramp_ps,external_load_pf=load_pf,ports=ports))
    assert cases and sequential
    deck=out/'batch.cir'
    lines=[f'* Extracted combinational batch only: {len(cases)} independent fixtures.',
        f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {args.corner}',
        *[f'.include "{p}"' for p in definitions],f'.options device temp={args.temperature_c}',
        '.options timeint reltol=1e-5 abstol=1e-10','VSUP VDD 0 1.8']
    columns=[]
    for i,case in enumerate(cases):
        aliases={**SUPPLIES,case['input']:f'IN_{i}',case['output']:f'OUT_{i}',
                 **{p:'VDD' if v else '0' for p,v in case['side_inputs'].items()}}
        lines.extend([f'VIN_{i} IN_{i} 0 PULSE(0 1.8 2n {case["full_ramp_ps"]:.12g}p {case["full_ramp_ps"]:.12g}p 5n 16n)',
            f'XDUT_{i} '+ ' '.join(aliases[p] for p in case['ports'])+' '+case['master']])
        if case['external_load_pf']>0:lines.append(f'CLOAD_{i} OUT_{i} 0 {case["external_load_pf"]:.12g}p')
        columns.extend([f'V(IN_{i})',f'V(OUT_{i})'])
    lines.extend(['.tran 2p 34n 0 2p','.print tran '+' '.join(columns),'.end'])
    deck.write_text('\n'.join(lines)+'\n');pins[str(deck)]=sha(deck)
    save(out/'plan.json',dict(pvt=dict(corner=args.corner,supply_v=1.8,temperature_c=args.temperature_c),
        fixtures=cases,independent_truth_table_rows_checked=truth_rows,sequential_cells_not_characterized=sequential,
        input_sha256=pins,per_check_timeout_s=43200,automatic_identical_retry=False,
        native_processes=1,physical_timing_qualified=False,release_qualified=False,scope=__doc__))
    print(f'Prepared {len(cases)} fixtures across {len(definitions)} combinational types',flush=True)
    if not args.run:return
    for path,digest in pins.items():assert sha(path)==digest,path
    admit_one(out)
    with (out/'run.log').open('x') as stream:
        child=subprocess.Popen([str(XYCE),'-linsolv','KLU','-quiet','-o',str(out/'batch'),str(deck)],
            stdout=stream,stderr=subprocess.STDOUT)
        save(out/'launch.json',dict(pid=child.pid,started_utc=datetime.now(timezone.utc).isoformat(),
             command=[str(XYCE),'-linsolv','KLU','-quiet','-o',str(out/'batch'),str(deck)],release_qualified=False))
        try:code=child.wait(timeout=max(.001,43200-(time.monotonic()-started)))
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.wait(timeout=30)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            save(out/'timeout.json',dict(inconclusive=True,release_qualified=False));raise
    assert code==0,(out/'run.log').read_text()[-2000:]
    wave=out/'batch.prn';times=[];values=[[] for _ in columns];terminal=False
    with wave.open() as stream:
        assert stream.readline().split()==['Index','TIME',*columns]
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:terminal=True;continue
            row=line.split()
            if not row:continue
            assert row[0].isdigit() and int(row[0])==len(times)
            numbers=list(map(float,row));assert len(numbers)==len(columns)+2 and all(map(math.isfinite,numbers))
            times.append(numbers[1])
            for values_column,value in zip(values,numbers[2:]):values_column.append(value)
    assert terminal and times[0]==0 and times[-1]>=34e-9-1e-15 and all(a<b for a,b in zip(times,times[1:]))
    records=[]
    for i,case in enumerate(cases):
        incoming,outgoing=values[2*i:2*i+2];record=dict(case_index=i,passed=False)
        try:
            assert min(outgoing)<.18 and max(outgoing)>1.62
            for rising in (False,True):
                starts=crossings(times,incoming,.9,rising)
                ends=crossings(times,outgoing,.9,rising!=case['inverted'])
                assert len(starts)==2 and len(ends)==2
                delays=[]
                for t in starts:
                    matched=[u for u in ends if t-1e-9<u<t+5e-9];assert len(matched)==1
                    delays.append((matched[0]-t)*1e9)
                record['input_rise_delay_ns' if rising else 'input_fall_delay_ns']=delays
            record['passed']=True
        except AssertionError:record['reason']='threshold/rail/event correspondence failed'
        records.append(record)
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        fixtures=len(cases),passing=sum(r['passed'] for r in records),records=records,
        all_native_waveform_events_terminal=True,physical_timing_qualified=False,release_qualified=False,
        scope=__doc__))
    print(f'Measured {len(cases)} fixtures, passing {sum(r["passed"] for r in records)}',flush=True)


if __name__=='__main__':main()
