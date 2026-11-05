"""Native conventional-capacitance BBPD observations; parent/receiver/R qualification remains open."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT,PROFILE,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from assess_prototype_native_waveform import crossings


def table(text):
    declared=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',text)
    if len(declared)!=1:raise ValueError('one native transient table required')
    rows=[]
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].isdigit():continue
        if len(f)!=7 or int(f[0])!=len(rows):raise ValueError('malformed or incomplete native table')
        values=tuple(map(float,f[1:]))
        if not all(math.isfinite(v) for v in values) or (rows and values[0]<=rows[-1][0]):raise ValueError('nonfinite/nonmonotone waveform')
        rows.append(values)
    if len(rows)!=int(declared[0]) or not rows or rows[0][0]!=0 or rows[-1][0]<90e-9-1e-15:raise ValueError('incomplete 90 ns waveform')
    return rows


def metrics(rows,phase_ps):
    def edges(column,threshold):return crossings([(r[0],r[column]) for r in rows],threshold)
    ref=edges(1,.9)[0];div=edges(2,.9)[0]
    if len(ref)!=2 or len(div)!=2:raise ValueError('two reference and divided-clock samples required')
    if any(abs(t-target*1e-9)>1e-12 for t,target in zip(ref,(10.1,50.1))):raise ValueError('reference frequency or start time mismatch')
    if any(abs((b-a)*1e12-phase_ps)>1 for a,b in zip(ref,div)):raise ValueError('observed phase does not match fixture')
    release=edges(3,.9)[0]
    if len(release)!=1 or abs(release[0]-1.1e-9)>1e-12:raise ValueError('reset release waveform mismatch')
    result={}
    for column,name in ((4,'DN'),(5,'UP')):
        rise,fall=edges(column,.9)
        selected_rise=[t for t in rise if t>=5e-9];selected_fall=[t for t in fall if t>=5e-9]
        widths=[]
        for t in selected_rise:
            following=[f for f in selected_fall if f>t]
            if following:widths.append((following[0]-t)*1e12)
        slews={}
        for direction,label in ((0,'rise'),(1,'fall')):
            lo=edges(column,.36)[direction];hi=edges(column,1.44)[direction]
            first,second=(lo,hi) if direction==0 else (hi,lo)
            samples=[]
            for t in first:
                if t<5e-9:continue
                following=[h for h in second if h>=t]
                if following:samples.append((following[0]-t)*1e12)
            slews[label]=samples
        quiet=[r[column] for r in rows if 5e-9<=r[0]<=8e-9]
        result[name]=dict(rising_edges_ns=[t*1e9 for t in selected_rise],falling_edges_ns=[t*1e9 for t in selected_fall],
            complete_high_pulse_widths_ps=widths,output_slew_20_to_80_ps=slews,
            quiet_before_first_sample=bool(quiet) and max(quiet)<.36,
            observed_voltage_interval_v=[min(r[column] for r in rows),max(r[column] for r in rows)])
    return dict(phase_ps=phase_ps,measured_clock_phase_ps=[(b-a)*1e12 for a,b in zip(ref,div)],outputs=result,
        expected_pulse_polarity_qualified=False,receiver_capture_qualified=False)


def run(output,corner,phases):
    if len(set(phases))!=len(phases) or not phases or any(not -1000<=p<=1000 for p in phases):raise ValueError('unique phase offsets within +/-1000 ps required')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',BLIS_NUM_THREADS='1')
    source=ROOT/'build/signoff400/prototype_v3_analog_capacitance_002'
    receipt=source/'native_assessment.json';netlist=source/'IntegerPLL_BBPD/capacitance.spice';r=json.loads(receipt.read_text())
    if r['artifacts'].get(str(netlist))!=sha(netlist):raise ValueError('native extracted model changed')
    header=subcircuits(netlist.read_text())['IntegerPLL_BBPD'].splitlines()[0].split()[2:]
    binding={'BBPD[0]':'DN','BBPD[1]':'UP','CLKDIVR':'DIV','REF':'REF','RESET_N':'RESET','VGND':'0','VNB':'0','VPB':'VDD','VPWR':'VDD'}
    if set(header)!=set(binding):raise ValueError('unexpected detector interface')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pins={str(p):sha(p) for p in (PROFILE,receipt,netlist,image,ng,Path(__file__).resolve(),Path(__file__).with_name('assess_prototype_native_waveform.py'))}
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    artifacts={};records=[];failures=[]
    save(output/'input_manifest.json',dict(input_sha256=pins,corner=corner,phase_ps=phases,output_load_fF=20,full_input_ramp_ps=200,
        temperature_c=27,supply_v=1.8,parent_coupling_included=False,distributed_R_included=False,actual_receivers_included=False))
    for phase in phases:
        folder=output/('phase_'+str(phase)+'ps');folder.mkdir();init=folder/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
        deck=folder/'detector.cir';deck.write_text(f'''* Conventional extracted BBPD phase observation
.lib "{pdk}" {corner}
.include "{netlist}"
.temp 27
.option klu method=gear reltol=1e-5 abstol=1e-9 num_threads=1
.width out=240
VDD VDD 0 1.8
VRESET RESET 0 PWL(0 0 1n 0 1.2n 1.8)
VREF REF 0 PULSE(0 1.8 10n 200p 200p 19.8n 40n)
VDIV DIV 0 PULSE(0 1.8 {10+phase/1000:.12g}n 200p 200p 19.8n 40n)
XBBPD {' '.join(binding[p] for p in header)} IntegerPLL_BBPD
CDN DN 0 20f
CUP UP 0 20f
.tran 10p 90n 0 10p
.print tran v(REF) v(DIV) v(RESET) v(DN) v(UP)
.end
''')
        save(output/'status.json',dict(state='native_BBPD_phase_running',phase_ps=phase,completed=len(records),failed=len(failures),release_ready=False))
        log=folder/'native.log'
        try:
            with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',folder,image,ng,'-b',deck],log,min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+1800),4)
            text=log.read_text()
            if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('KLU selection not observed')
            records.append(metrics(table(text),phase))
        except (ValueError,RuntimeError,TimeoutError) as exc:failures.append(dict(phase_ps=phase,reason=repr(exc)))
        for p in (init,deck,log):
            if p.exists():artifacts[str(p)]=sha(p)
    verify(pins);detail=output/'observations.json';save(detail,dict(results=records,failures=failures));artifacts[str(detail)]=sha(detail)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,corner=corner,required_cases=len(phases),completed_cases=len(records),
        all_declared_native_waveforms_complete=len(records)==len(phases) and not failures,output_load_fF=20,full_input_ramp_ps=200,
        parent_coupling_included=False,distributed_R_included=False,actual_receivers_included=False,numerical_convergence_qualified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='BBPD_phase_screen_terminal',completed=len(records),failed=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True)
    p.add_argument('--phases-ps',type=int,nargs='+',default=[-1000,0,1000]);a=p.parse_args();run(a.output.resolve(),a.corner,a.phases_ps)
