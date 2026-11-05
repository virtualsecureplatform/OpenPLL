"""Replay an observed event-wire glitch into the actual first synchronizer cell."""
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
from run_prototype_BBPD_receiver_RC_point import read_table
from assess_prototype_native_waveform import crossings


def replay_points(rows,column,high):
    points=[(0,1.8 if high else 0),(4.9e-9,1.8 if high else 0)]
    sample=[(r[0],1.8-r[column] if high else r[column]) for r in rows if 5e-9<=r[0]<=8e-9]
    if len(sample)<200 or sample[-1][0]-sample[0][0]<2.98e-9:raise ValueError('complete quiet glitch interval required')
    if not all(math.isfinite(v) for _,v in sample):raise ValueError('nonfinite replay')
    return points+sample+[(8.1e-9,1.8 if high else 0),(12e-9,1.8 if high else 0)]


def assess(rows,high):
    values=[r[3] for r in rows if 4e-9<=r[0]<=11e-9]
    if not values:raise ValueError('missing replay observation window')
    rise,fall=crossings([(r[0],r[3]) for r in rows],.9)
    edges=[t for t in rise+fall if 4e-9<=t<=11e-9]
    return dict(minimum_Q_V=min(values),maximum_Q_V=max(values),unexpected_threshold_crossings=len(edges),
                state_retained=not edges and (min(values)>=1.62 if high else max(values)<=.18))


def run(source,output,corner):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r.get('all_declared_native_waveforms_complete') or r.get('aggressor_phase_ps',-1)<0:raise ValueError('completed nonquiet native source required')
    log=source/'phase_0ps/native.log'
    if r['artifacts'].get(str(log))!=sha(log):raise ValueError('unbound replay waveform')
    rows=read_table(log.read_text())
    extraction=ROOT/'build/signoff400/prototype_v3_assembly_capacitance_001'
    er=extraction/'native_assessment.json';netlist=extraction/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    if json.loads(er.read_text())['artifacts'].get(str(netlist))!=sha(netlist):raise ValueError('extracted cell changed')
    master='sky130_fd_sc_hs__dfrtp_1';block=subcircuits(netlist.read_text())[master]
    model=output/'cell.spice';model.write_text(block);ports=header(block)
    if any(l.lstrip().startswith('D') for l in block.splitlines()):raise ValueError('diode geometry review required')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    paths=[receipt,log,er,netlist,model,image,ng,Path(__file__).resolve(),Path(__file__).with_name('run_prototype_BBPD_receiver_RC_point.py')]
    pins={str(p):sha(p) for p in paths};results=[];artifacts={str(model):sha(model)}
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    for high in (False,True):
        points=replay_points(rows,6,high)
        data='PWL('+' '.join(f'{t:.15g} {v:.15g}' for t,v in points)+')'
        for phase in range(0,3001,250):
            folder=output/f'{int(high)}_{phase}ps';folder.mkdir();init=folder/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
            center=5+phase/1000
            clk=f'PWL(0 0 2.99n 0 3.01n 1.8 3.49n 1.8 3.51n 0 {center-.01:.12g}n 0 {center+.01:.12g}n 1.8 {center+.49:.12g}n 1.8 {center+.51:.12g}n 0)'
            binding=dict(CLK='CLK',D='D',Q='Q',RESET_B='RESET',VPWR='VDD',VPB='VDD',VGND='0',VNB='0')
            deck=folder/'replay.cir';deck.write_text(f'''* Conditional replay of observed DN event-wire glitch; no interface qualification
.lib "{pdk}" {corner}
.include "{model}"
.temp 27
.option klu reltol=1e-5 abstol=1e-9 num_threads=1
.width out=200
VDD VDD 0 1.8
VRESET RESET 0 PWL(0 0 1n 0 1.02n 1.8)
VD D 0 {data}
VCLK CLK 0 {clk}
Xcell {' '.join(binding.get(p,'private_'+str(i)) for i,p in enumerate(ports))} {master}
CLOAD Q 0 2f
.tran 2p 12n 0 2p
.print tran v(CLK) v(D) v(Q)
.end
''')
            native=folder/'native.log';save(output/'status.json',dict(state='native_replay_running',corner=corner,completed=len(results),release_ready=False))
            with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',folder,image,ng,'-b',deck],native,min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+300),4)
            text=native.read_text();wave=[]
            if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('KLU selection required')
            for line in text.splitlines():
                f=line.split()
                if f and f[0].isdigit():
                    if len(f)!=5 or int(f[0])!=len(wave):raise ValueError('invalid replay waveform table')
                    wave.append(tuple(map(float,f[1:])))
            if not wave or wave[0][0]!=0 or wave[-1][0]<12e-9-1e-15:raise ValueError('incomplete replay horizon')
            results.append(dict(high=high,clock_center_ns=center,**assess(wave,high)))
            artifacts.update({str(p):sha(p) for p in (init,deck,native)})
    detail=output/'observations.json';save(detail,results);artifacts[str(detail)]=sha(detail);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,corner=corner,cases=len(results),
         all_replayed_states_retained=all(r['state_retained'] for r in results),
         waveform_source_corner=r['corner'],high_state_is_complemented_observation=True,
         output_load_fF=2,actual_pin_loading_in_original_waveform=False,phase_continuum_covered=False,
         diagnostic=True,native_interface_qualified=False,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='native_glitch_replay_complete',completed=len(results),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--corner',required=True,choices=('tt','ff','ss','sf','fs'));a=p.parse_args();run(a.source.resolve(),a.output.resolve(),a.corner)
