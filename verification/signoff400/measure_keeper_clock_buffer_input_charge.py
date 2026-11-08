"""Characterize extracted clock-buffer input current; build no causal load model yet."""
import json
import os
from pathlib import Path
import time
import numpy as np
from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from run_prototype_capture_boundaries_v3 import pwl,transition
from audit_keeper_DCO_driver_C_cut import capacitance


def integral(t,y,start,stop):
    if not start<stop or start<t[0] or stop>t[-1]:
        raise ValueError('integration window must lie inside complete trace')
    inside=(t>start)&(t<stop)
    times=np.concatenate(([start],t[inside],[stop]))
    values=np.concatenate(([np.interp(start,t,y)],y[inside],[np.interp(stop,t,y)]))
    return float(np.sum((values[:-1]+values[1:])*.5*np.diff(times)))


def observe(t,v,current,q,ramp_ps):
    ramp=ramp_ps*1e-12
    high=(t>=16e-9)&(t<=19e-9)
    low=(t>=30e-9)&(t<=33e-9)
    before=(t>=7e-9)&(t<=8e-9)
    if any(not np.any(m) for m in (high,low,before)):
        raise ValueError('complete stable-state windows required')
    state_pass=bool(np.all(q[high]>=1.62) and np.all(q[low]<=.18) and np.all(q[before]<=.18))
    charge=[-integral(t,current,8e-9,20e-9),integral(t,current,20e-9,33e-9)]
    cap=[-integral(t,current,10e-9-.3*ramp,10e-9+.3*ramp)/1.08,
          integral(t,current,22e-9-.3*ramp,22e-9+.3*ramp)/1.08]
    input_pass=bool(np.all(v[before]<=.18) and np.all(v[high]>=1.62) and np.all(v[low]<=.18))
    return dict(input_levels_verified=input_pass,noninverting_response_verified=state_pass,
                full_window_charge_C=charge,effective_20_80_capacitance_F=cap,
                maximum_absolute_input_current_A=float(np.max(np.abs(current))))


def run():
    base=ROOT/'build/signoff400'
    output=base/'selected_keeper_clock_buffer_charge_1526'
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{19})
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        extraction=base/'prototype_v3_fixed_divider_digital_capacitance_001'
        receipt=extraction/'assessment.json'
        source=extraction/'IntegerPLL_ProgrammedCore/capacitance.spice'
        a=json.loads(receipt.read_text())
        if a['artifacts'].get(str(source))!=sha(source):
            raise ValueError('unchanged extracted cell source required')
        master='sky130_fd_sc_hs__clkbuf_16'
        block=subcircuits(source.read_text())[master]
        ports=header(block)
        if not {'A','X','VPWR','VGND','VPB','VNB'}<=set(ports):
            raise ValueError('complete clock buffer interface required')
        if any(line.lstrip().startswith('D') for line in block.splitlines()):
            raise ValueError('diode units require separate review')
        model=output/'cell.spice'
        model.write_text(block)
        explicit=[]
        for line in block.splitlines():
            f=line.split()
            if f and f[0].startswith('C') and 'A' in f[1:3]:
                if len(f)!=4 or capacitance(f[3])<0:
                    raise ValueError('nonnegative literal input capacitance required')
                explicit.append(dict(name=f[0],nodes=f[1:3],literal=f[3],value_F_exact=str(capacitance(f[3]))))
        capfile=output/'explicit_input_capacitors.json'
        save(capfile,explicit)
        ng=ROOT/'build/tools/ngspice47_diode_charge_fix_001/ngspice'
        pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice')
        files=[receipt,source,model,capfile,ng,pdk,Path(__file__).resolve()]
        files += [Path(__file__).with_name(n) for n in ['prepare_prototype_analog_reference.py',
            'prepare_prototype_BBPD_receiver_v2.py','run_prototype_capture_boundaries_v3.py',
            'audit_keeper_DCO_driver_C_cut.py']]
        pins={str(p):sha(p) for p in files}
        cases=[dict(full_ramp_ps=r,output_load_fF=c) for r in (20,400,1600) for c in (0,100,400)]
        save(output/'plan.json',dict(master=master,cases=cases,corners=['tt','ff','ss','sf','fs'],
             CPU=19,memory_GiB=4,native_limit_s_per_corner=3600,maximum_step_ps=2,
             reference_capacitor_fF=20,reference_20_80_relative_tolerance=1e-4,
             full_current_includes_explicit_extracted_capacitance=True,
             automatic_identical_retry=False,release_ready=False))
        pins[str(output/'plan.json')]=sha(output/'plan.json')
        results,artifacts=[],{}
        for corner in ('tt','ff','ss','sf','fs'):
            target=output/corner
            target.mkdir()
            wave,deck=target/'waveform.dat',target/'charge.cir'
            body=[]
            for i,case in enumerate([*cases,dict(full_ramp_ps=400,output_load_fF=20)]):
                points=[(0,0),*transition(10,0,1,case['full_ramp_ps']),
                        *transition(22,1,0,case['full_ramp_ps']),(34,0)]
                body.append(f'VIN{i} A{i} 0 {pwl(points)}')
                if i==len(cases):
                    body.append(f'CCONTROL A{i} 0 20f')
                else:
                    aliases=dict(A=f'A{i}',X=f'Q{i}',VPWR='VDD',VPB='VDD',VGND='0',VNB='0')
                    body.append(f'XCELL{i} '+' '.join(aliases.get(p,f'PRIVATE_{i}_{j}') for j,p in enumerate(ports))+' '+master)
                    if case['output_load_fF']:
                        body.append(f'CQ{i} Q{i} 0 {case["output_load_fF"]}f')
            columns=[field for i in range(len(cases)) for field in (f'v(a{i})',f'i(vin{i})',f'v(q{i})')]
            columns += [f'v(a{len(cases)})',f'i(vin{len(cases)})']
            init=target/'.spiceinit'
            init.write_text('set ngbehavior=hsa\n')
            deck.write_text('\n'.join(['* Extracted clock-buffer input current grid',f'.lib "{pdk}" {corner}',
                 f'.include "{model}"','.temp 27','.option reltol=1e-6 abstol=1e-12 num_threads=1',
                 'VDD VDD 0 1.8',*body,'.control','set wr_singlescale','set wr_vecnames','set numdgt=15',
                 'tran 2p 34n 0 2p',f'wrdata {wave} '+' '.join(columns),'quit','.endc','.end'])+'\n')
            pins.update({str(p):sha(p) for p in [deck,init]})
            save(output/'status.json',dict(state='native_clock_buffer_input_current_running',corner=corner,release_ready=False))
            with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+86400):
                previous=Path.cwd()
                try:
                    os.chdir(target)
                    execute([ng,'-b',deck],target/'native.log',time.clock_gettime(time.CLOCK_BOOTTIME)+3600,4)
                finally:
                    os.chdir(previous)
            if [s.lower() for s in wave.open().readline().split()]!=['time',*columns]:
                raise ValueError('exact input-current waveform columns required')
            x=np.loadtxt(wave,skiprows=1)
            if (x.ndim!=2 or x.shape[1]!=1+len(columns) or not np.isfinite(x).all()
                    or x[0,0]!=0 or abs(x[-1,0]-34e-9)>1e-15 or not np.all(np.diff(x[:,0])>0)):
                raise ValueError('complete finite ordered current waveform required')
            t=x[:,0]
            control_current=x[:,-1]
            control=[-integral(t,control_current,9.88e-9,10.12e-9)/1.08,
                      integral(t,control_current,21.88e-9,22.12e-9)/1.08]
            if any(abs(v/20e-15-1)>1e-4 for v in control):
                raise ValueError('known 20 fF capacitance sign and unit control failed')
            for i,case in enumerate(cases):
                results.append(dict(corner=corner,**case,**observe(t,x[:,1+3*i],x[:,2+3*i],x[:,3+3*i],case['full_ramp_ps']),
                                    reference_capacitances_F=control))
            artifacts.update({str(p):sha(p) for p in [wave,target/'native.log']})
        detail=output/'observations.json'
        save(detail,results)
        artifacts[str(detail)]=sha(detail)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
             master=master,cases=len(results),all_reference_capacitor_controls_pass=True,
             all_input_levels_verified=all(r['input_levels_verified'] for r in results),
             all_noninverting_responses_verified=all(r['noninverting_response_verified'] for r in results),
             explicit_input_C_deembedding_complete=False,causal_receiver_model_available=False,
             numerical_convergence_qualified=False,actual_routed_load_envelope_qualified=False,
             clock_receiver_model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='native_clock_buffer_input_charge_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise


if __name__=='__main__':
    run()
