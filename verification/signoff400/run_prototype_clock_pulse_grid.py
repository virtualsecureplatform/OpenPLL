"""Observe used extracted flip-flops under short high/low clock pulses in independent fixtures."""
import argparse
import json
import math
import os
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from assess_prototype_native_waveform import crossings

LOADS={'dfrtp_1':100,'dfrtp_2':150,'dfrtp_4':250,'dfstp_1':50,'dfstp_4':250}
WIDTHS=(250,400,600,1000,1600)


def waveform(path,n):
    lines=path.read_text().splitlines()
    if lines[0].split()!=['time']+[f'v(q{i})' for i in range(n)]+[f'v(clk{i})' for i in range(n)]:raise ValueError('unexpected pulse-grid waveform columns')
    rows=[]
    for line in lines[1:]:
        row=tuple(map(float,line.split()))
        if len(row)!=1+2*n or not all(math.isfinite(v) for v in row) or rows and row[0]<=rows[-1][0]:raise ValueError('invalid pulse-grid samples')
        rows.append(row)
    if not rows or rows[0][0]!=0 or abs(rows[-1][0]-14e-9)>1e-15:raise ValueError('incomplete pulse-grid horizon')
    return rows


def assess(rows,kind,index,n):
    old=int(kind=='low');new=1-old
    pre=[r[index+1] for r in rows if 4.5e-9<=r[0]<=5e-9]
    final=[r[index+1] for r in rows if 12e-9<=r[0]<=13e-9]
    def stable(v,state):return bool(v) and (min(v)>=1.62 if state else max(v)<=.18)
    rises,falls=crossings([(r[0],r[index+1]) for r in rows],.9)
    edges=[(t,'rise') for t in rises if t>=5e-9]+[(t,'fall') for t in falls if t>=5e-9]
    cr,cf=crossings([(r[0],r[1+n+index]) for r in rows],.9)
    pairs=[(b-a)*1e12 for a in (cr if kind=='high' else cf) for b in (cf if kind=='high' else cr) if a>=5e-9 and b>a]
    return dict(pre_state_verified=stable(pre,old),final_state_verified=stable(final,new),
        full_output_trace_capture_verified=stable(pre,old) and stable(final,new) and len(edges)==1 and edges[0][1]==('rise' if new else 'fall'),
        observed_clock_pulse_width_ps=min(pairs) if pairs else None,
        output_edges_ns=[dict(time=t*1e9,direction=d) for t,d in sorted(edges)])


def run(output,corner,short):
    master='sky130_fd_sc_hs__'+short;load=LOADS[short];output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    ext=ROOT/'build/signoff400/prototype_v3_assembly_capacitance_001';er=ext/'native_assessment.json';source=ext/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    if json.loads(er.read_text())['artifacts'].get(str(source))!=sha(source):raise ValueError('extracted cell changed')
    block=subcircuits(source.read_text())[master];model=output/'cell.spice';model.write_text(block);ports=header(block)
    if any(l.lstrip().startswith('D') for l in block.splitlines()):raise ValueError('diode units require explicit review')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pins={str(p):sha(p) for p in (er,source,model,image,ng,Path(__file__).resolve())};cases=[(kind,width) for kind in ('high','low') for width in WIDTHS];body=[]
    for i,(kind,width) in enumerate(cases):
        w=width/1000
        clock=(f'PWL(0 0 2.9n 0 3.1n 1.8 3.9n 1.8 4.1n 0 5.9n 0 6.1n 1.8 {6+w-.1:.12g}n 1.8 {6+w+.1:.12g}n 0)' if kind=='high' else
               f'PWL(0 0 2.9n 0 3.1n 1.8 5.9n 1.8 6.1n 0 {6+w-.1:.12g}n 0 {6+w+.1:.12g}n 1.8)')
        data='PWL(0 0 3.9n 0 4.1n 1.8)' if kind=='high' else 'PWL(0 1.8 5.4n 1.8 5.6n 0)'
        binding=dict(CLK=f'CLK{i}',D=f'D{i}',Q=f'Q{i}',RESET_B='CTRL',SET_B='CTRL',VGND='0',VNB='0',VPB='VDD',VPWR='VDD')
        body += [f'VCLK{i} CLK{i} 0 {clock}',f'VD{i} D{i} 0 {data}',f'Xcell{i} '+ ' '.join(binding.get(p,f'private_{i}_{j}') for j,p in enumerate(ports))+' '+master,f'CLOAD{i} Q{i} 0 {load}f']
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    data=output/'waveform.dat';deck=output/'pulse_grid.cir';init=output/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
    deck.write_text('\n'.join(['* Independent clock pulse capture fixtures',f'.lib "{pdk}" {corner}',f'.include "{model}"','.temp 27','.option klu reltol=1e-5 abstol=1e-9 num_threads=1','VDD VDD 0 1.8','VCTRL CTRL 0 PWL(0 0 1n 0 1.2n 1.8)',*body,'.control','set wr_singlescale','set wr_vecnames','set numdgt=15','tran 2p 14n 0 2p',f'wrdata {data} '+' '.join([f'v(q{i})' for i in range(len(cases))]+[f'v(clk{i})' for i in range(len(cases))]),'quit','.endc','.end'])+'\n')
    pins.update({str(p):sha(p) for p in (deck,init)});save(output/'status.json',dict(state='native_clock_pulse_grid_running',release_ready=False))
    with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',output,image,ng,'-b',deck],output/'native.log',deadline,4)
    rows=waveform(data,len(cases));results=[dict(kind=k,nominal_width_ps=w,**assess(rows,k,i,len(cases))) for i,(k,w) in enumerate(cases)]
    detail=output/'observations.json';save(detail,results);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (data,detail,output/'native.log')},corner=corner,master=master,cases=len(cases),load_fF=load,clock_full_ramp_ps=200,
         all_grid_captures_verified=all(r['full_output_trace_capture_verified'] for r in results),
         final_pin_load_and_clock_slew_envelope_verified=False,all_reachable_startup_frequencies_covered=False,
         diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='native_clock_pulse_grid_complete',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--corner',required=True,choices=('tt','ff','ss','sf','fs'));p.add_argument('--master',required=True,choices=tuple(LOADS));a=p.parse_args();run(a.output.resolve(),a.corner,a.master)
