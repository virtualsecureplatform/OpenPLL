"""Observe a used flip-flop's nominal capture boundaries; qualify no timing constraints."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from resources import identity,lease

OFFSETS=(-1000,-500,-200,0,200,500,1000)


def transition(center,before,after):return [(center-.1,before*1.8),(center+.1,after*1.8)]
def pwl(points):return 'PWL('+' '.join(f'{t:.12g}n {v:.12g}' for t,v in points)+')'
def value(log,name):
    m=re.search(r'^\s*'+name+r'\s*=\s*([-+0-9.eE]+)',log,re.M|re.I)
    return float(m[1]) if m else None

def logic(low,high):
    if low is None or high is None:return None
    return 0 if high<=.18 else 1 if low>=1.62 else None


def run(output,corner,master,ngspice):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='1')
    source=ROOT/'build/signoff400/prototype_v3_assembly_capacitance_001';receipt=source/'native_assessment.json';r=json.loads(receipt.read_text())
    netlist=source/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    if r['artifacts'].get(str(netlist))!=sha(netlist):raise ValueError('final assembled cell source changed')
    model=output/'cell.spice';block=subcircuits(netlist.read_text())[master];model.write_text(block)
    header=[]
    for line in block.splitlines():
        if not header:header=line.split()[2:]
        elif line.startswith('+'):header+=line.split()[1:]
        else:break
    control='RESET_B' if '__dfrtp_' in master else 'SET_B';reset_value=0 if control=='RESET_B' else 1
    functional={'CLK','D','Q',control,'VGND','VNB','VPB','VPWR'}
    if not functional.issubset(header):raise ValueError('missing functional sequential cell interface')
    private=[p for p in header if p not in functional]
    if any(not re.fullmatch(r'a_\d+_\d+#',p) for p in private):raise ValueError('unreviewed exposed internal port')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ngspice
    paths=[receipt,netlist,image,ng,model,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    results=[];artifacts={str(model):sha(model)}
    for kind in ('data_rise','data_fall','async_release'):
        for offset in OFFSETS:
            folder=output/f'{kind}_{offset}ps';folder.mkdir();(folder/'.spiceinit').write_text('set ngbehavior=hsa\n')
            clock=[(0,0)]
            for t in (10,20):clock+=transition(t,0,1)+transition(t+2,1,0)
            if kind=='async_release':
                old=reset_value;new=1-old;data=[(0,new*1.8)];ctrl=[(0,0)]+transition(20+offset/1000,0,1)
            else:
                new=int(kind=='data_rise');old=1-new;data=[(0,old*1.8)]+transition(20+offset/1000,old,new);ctrl=[(0,0)]+transition(2,0,1)
            binding={'VPWR':'VDD','VPB':'VDD','VGND':'0','VNB':'0','CLK':'CLK','D':'D','Q':'Q',control:'CTRL'}
            deck=folder/'capture.cir';deck.write_text(f'''* Prototype capture observation {master} {kind} {offset}ps
.lib "{pdk}" {corner}
.include "{model}"
.temp 27
.option klu
.option reltol=1e-5 abstol=1e-15 num_threads=1 numdgt=15
.width out=200
VDD VDD 0 1.8
VCLK CLK 0 {pwl(clock)}
VD D 0 {pwl(data)}
VCTRL CTRL 0 {pwl(ctrl)}
Xcell {' '.join(binding.get(p,'__private_'+str(i)) for i,p in enumerate(header))} {master}
Cload Q 0 20f
.tran 10p 30n 0 10p
.meas tran pre_min MIN v(Q) FROM=17.5n TO=18.5n
.meas tran pre_max MAX v(Q) FROM=17.5n TO=18.5n
.meas tran final_min MIN v(Q) FROM=27n TO=28n
.meas tran final_max MAX v(Q) FROM=27n TO=28n
.print tran v(CLK) v(D) v(CTRL) v(Q)
.end
''')
            save(output/'status.json',dict(state='native_small_cell_capture_running',kind=kind,offset_ps=offset,completed=len(results),release_ready=False))
            log=folder/'native.log';error=None
            try:
                with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',folder,image,ng,'-b',deck],log,min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+120),4)
            except (RuntimeError,TimeoutError) as exc:error=repr(exc)
            text=log.read_text() if log.exists() else ''
            if error is None and 'Using KLU as Direct Linear Solver' not in text:raise ValueError('KLU backend selection missing')
            pre=logic(value(text,'pre_min'),value(text,'pre_max'));final=logic(value(text,'final_min'),value(text,'final_max'))
            sentinel=abs(offset)==1000;expected=(new if offset<0 else old) if sentinel else None
            results.append(dict(kind=kind,offset_ps=offset,native_completed=error is None,error=error,pretest_value=pre,pretest_expected=old,final_value=final,
                outcome='ambiguous_or_unsettled' if final is None else 'changed_value' if final==new else 'pretest_value',
                separated_control=sentinel,separated_control_pass=(error is None and pre==old and final==expected) if sentinel else None))
            for p in (deck,log,folder/'.spiceinit'):
                if p.exists():artifacts[str(p)]=sha(p)
    detail=output/'observations.json';save(detail,results);artifacts[str(detail)]=sha(detail);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,corner=corner,temperature_c=27,supply_v=1.8,master=master,
        fixtures=len(results),native_completed=sum(x['native_completed'] for x in results),
        separated_controls=sum(x['separated_control'] for x in results),separated_controls_pass=all(x['separated_control_pass'] for x in results if x['separated_control']),
        input_slew_ps=200,output_load_fF=20,exposed_internal_ports_bound_to_private_nodes=private,external_intercell_coupling_included=False,setup_hold_recovery_removal_qualified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='capture_observations_complete_review_pending',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ngspice',type=Path,required=True)
    p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True)
    p.add_argument('--master',choices=('sky130_fd_sc_hs__dfrtp_1','sky130_fd_sc_hs__dfrtp_2','sky130_fd_sc_hs__dfrtp_4','sky130_fd_sc_hs__dfstp_1','sky130_fd_sc_hs__dfstp_4'),required=True)
    a=p.parse_args();run(a.output.resolve(),a.corner,a.master,a.ngspice.resolve())
