"""Capture CDC behavior under a 500MHz clock train with one-ns high pulses.

Observed rail resolution before the next edge is reviewed separately.
"""
import argparse
import json
import math
import os
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from run_prototype_capture_boundaries_v3 import transition,pwl,logic
from run_prototype_clock_pulse_grid import LOADS
from assess_prototype_clock_train_capture import analyze

OFFSETS=(-1500,-1000,-750,-500,-400,-300,-200,-150,-100,-75,-50,-25,0,25,50,75,100,150,200,300,400,500,750,1000,1500)


def table(path,n):
    lines=path.read_text().splitlines();expected=['time','v(clk)']+[f'v(q{i})' for i in range(n)]+[f'v(d{i})' for i in range(n)]+[f'v(ctrl{i})' for i in range(n)]
    if lines[0].split()!=expected:raise ValueError('capture refinement columns differ')
    rows=[]
    for line in lines[1:]:
        row=tuple(map(float,line.split()))
        if len(row)!=2+3*n or not all(math.isfinite(v) for v in row) or rows and row[0]<=rows[-1][0]:raise ValueError('invalid refinement samples')
        rows.append(row)
    if not rows or rows[0][0]!=0 or abs(rows[-1][0]-30e-9)>1e-15:raise ValueError('incomplete refinement capture')
    return rows


def run(output,corner,short,data_ramp_ps,clock_ramp_ps,extraction,load):
    if data_ramp_ps not in (20,200,2000) or clock_ramp_ps not in (20,200,400):raise ValueError('unsupported routed slew rectangle corner')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    master='sky130_fd_sc_hs__'+short
    receipt=extraction/'assessment.json';source=extraction/'IntegerPLL_ProgrammedCore/capacitance.spice'
    record=json.loads(receipt.read_text())
    if record['artifacts'].get(str(source))!=sha(source):raise ValueError('final extracted sequential cell changed')
    if load<=0 or not math.isfinite(load):raise ValueError('positive explicit output load required')
    block=subcircuits(source.read_text())[master];ports=header(block);model=output/'cell.spice';model.write_text(block)
    if any(line.lstrip().startswith('D') for line in block.splitlines()):raise ValueError('diode geometry requires explicit review')
    control='RESET_B' if short.startswith('dfrtp') else 'SET_B';reset_value=int(control=='SET_B')
    cases=[(kind,offset) for kind in ('data_rise','data_fall','async_release') for offset in OFFSETS];body=[];metadata=[]
    clock=[(0,0)]
    for t in range(10,30,2):clock+=transition(t,0,1,clock_ramp_ps)+transition(t+1,1,0,clock_ramp_ps)
    for i,(kind,offset) in enumerate(cases):
        if kind=='async_release':
            old=reset_value;new=1-old;data=[(0,new*1.8)];ctrl=[(0,0)]+transition(20+offset/1000,0,1,data_ramp_ps)
        else:
            new=int(kind=='data_rise');old=1-new;data=[(0,old*1.8)]+transition(20+offset/1000,old,new,data_ramp_ps);ctrl=[(0,0)]+transition(2,0,1)
        binding=dict(CLK='CLK',D=f'D{i}',Q=f'Q{i}',VGND='0',VNB='0',VPWR='VDD',VPB='VDD');binding[control]=f'CTRL{i}'
        private=[p for p in ports if p not in binding]
        import re
        if any(not re.fullmatch(r'a_\d+_\d+#',p) for p in private):raise ValueError('unreviewed extracted cell port')
        body += [f'VD{i} D{i} 0 '+pwl(data),f'VCTRL{i} CTRL{i} 0 '+pwl(ctrl),f'Xcell{i} '+' '.join(binding.get(p,f'private_{i}_{j}') for j,p in enumerate(ports))+' '+master,f'CLOAD{i} Q{i} 0 {load}f']
        metadata.append(dict(kind=kind,offset_ps=offset,pretest_expected=old,new_value=new,separated_control=False))
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    vectors=['v(clk)']+[f'v(q{i})' for i in range(len(cases))]+[f'v(d{i})' for i in range(len(cases))]+[f'v(ctrl{i})' for i in range(len(cases))]
    wave=output/'waveform.dat';deck=output/'refinement.cir';init=output/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
    deck.write_text('\n'.join(['* Independent off-grid capture refinement fixtures',f'.lib "{pdk}" {corner}',f'.include "{model}"','.temp 27','.option klu reltol=1e-6 abstol=1e-10 num_threads=1','VDD VDD 0 1.8','VCLK CLK 0 '+pwl(clock),*body,'.control','set wr_singlescale','set wr_vecnames','set numdgt=15','save '+' '.join(vectors),'tran 2.5p 30n 0 2.5p',f'wrdata {wave} '+' '.join(vectors),'quit','.endc','.end'])+'\n')
    paths=[receipt,source,model,image,ng,deck,init,Path(__file__).resolve(),Path(__file__).with_name('run_prototype_capture_boundaries_v3.py'),Path(__file__).with_name('assess_prototype_clock_train_capture.py')];pins={str(p):sha(p) for p in paths}
    save(output/'input_manifest.json',dict(input_sha256=pins,corner=corner,master=master,load_fF=load,input_full_ramp_ps=data_ramp_ps,clock_full_ramp_ps=clock_ramp_ps,maximum_step_ps=2.5,clock_period_ns=2,clock_high_ns=1,pre_next_edge_observation_end_ns=21.8,cases=metadata))
    save(output/'status.json',dict(state='native_offgrid_capture_running',release_ready=False))
    log=output/'native.log'
    with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',output,image,ng,'-b',deck],log,deadline,4)
    if 'Using KLU as Direct Linear Solver' not in log.read_text():raise ValueError('KLU selection required')
    rows=table(wave,len(cases));records=[]
    for i,case in enumerate(metadata):
        projected=[(r[0],r[1],r[2+len(cases)+i],r[2+2*len(cases)+i],r[2+i]) for r in rows]
        pre=[r[4] for r in projected if 17.5e-9<=r[0]<=18e-9];final=[r[4] for r in projected if 21.5e-9<=r[0]<=21.8e-9]
        a=logic(min(pre),max(pre));b=logic(min(final),max(final))
        observed=dict(case,pretest_value=a,final_value=b,outcome='ambiguous_or_unsettled' if b is None else 'changed_value' if b==case['new_value'] else 'pretest_value')
        metrics=analyze(projected,observed)
        if abs(metrics['measured_changing_input_slew_20_to_80_ps']-.6*data_ramp_ps)>1:raise ValueError('refinement input slew differs')
        records.append(dict(**observed,waveform_metrics=metrics))
    detail=output/'observations.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (wave,log,detail)},corner=corner,master=master,load_fF=load,cases=len(cases),
        all_pretest_states_verified=all(r['pretest_value']==r['pretest_expected'] for r in records),
        minimum_phase_grid_spacing_ps=25,input_full_ramp_ps=data_ramp_ps,clock_full_ramp_ps=clock_ramp_ps,clock_period_ns=2,clock_high_ns=1,load_is_characterization_point_not_qualified_bound=True,constraints_qualified=False,load_and_slew_envelope_verified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='native_offgrid_capture_complete',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--extraction',required=True,type=Path)
    p.add_argument('--corner',required=True,choices=('tt','ff','ss','sf','fs'))
    p.add_argument('--master',required=True,choices=('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_2'))
    p.add_argument('--load-ff',required=True,type=float)
    p.add_argument('--data-ramp-ps',required=True,type=int,choices=(20,200,2000))
    p.add_argument('--clock-ramp-ps',required=True,type=int,choices=(20,200,400))
    a=p.parse_args();run(a.output.resolve(),a.corner,a.master,a.data_ramp_ps,a.clock_ramp_ps,a.extraction.resolve(),a.load_ff)
