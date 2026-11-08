"""Test the frozen charge surface on a prospective periodic native fixture."""
import json
import os
from pathlib import Path
import time
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from prepare_prototype_BBPD_receiver_v2 import header
from run_prototype_capture_boundaries_v3 import pwl,transition
from measure_keeper_clock_buffer_input_charge import integral
from fit_keeper_receiver_charge_surface import features,intrinsic_charge


def run():
    base=ROOT/'build/signoff400'
    training=base/'selected_keeper_clock_buffer_charge_deembedded_1527'
    fitted=base/'selected_keeper_receiver_charge_surface_1529'
    output=base/'selected_keeper_receiver_periodic_validation_1530'
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{19})
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    try:
        receipts=[p/'assessment.json' for p in (training,fitted)]
        records=[json.loads(p.read_text()) for p in receipts]
        for r in records:
            verify(r['input_sha256']);verify(r['artifacts'])
        validation=json.loads((fitted/'plan.json').read_text())['prospective_validation']
        if validation!={'input_full_ramp_ps':100,'output_load_fF':200,'frequency_MHz':400}:
            raise ValueError('unchanged prospective holdout required')
        model=training/'cell.spice'
        ports=header(model.read_text())
        caps=json.loads((training/'explicit_input_capacitors.json').read_text())
        surfaces=json.loads((fitted/'charge_surfaces.json').read_text())
        ng=ROOT/'build/tools/ngspice47_diode_charge_fix_001/ngspice'
        pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice')
        files=[*receipts,fitted/'plan.json',fitted/'charge_surfaces.json',model,
               training/'explicit_input_capacitors.json',ng,pdk,ROOT/'build/apptainer/openpll-release-modern.sif',
               Path(__file__).resolve()]
        files += [Path(__file__).with_name(n) for n in ['fit_keeper_receiver_charge_surface.py',
            'measure_keeper_clock_buffer_input_charge.py','run_prototype_capture_boundaries_v3.py']]
        pins={str(p):sha(p) for p in files}
        save(output/'plan.json',dict(input_sha256=pins,**validation,maximum_step_ps=1,
             corners=['tt','ff','ss','sf','fs'],native_cases=5,CPU=19,memory_GiB=4,
             frozen_coefficients=True,internal_voltage_still_observed_not_predicted=True,
             automatic_identical_retry=False,release_ready=False))
        points=[(0,0)]
        for k in range(12):
            points+=transition(5+2.5*k,0,1,100)
            points+=transition(6.25+2.5*k,1,0,100)
        points.append((34,0))
        waveform=pwl(points)
        results=[];artifacts={}
        for corner in ('tt','ff','ss','sf','fs'):
            directory=output/corner;directory.mkdir()
            data,deck=directory/'waveform.dat',directory/'periodic.cir'
            aliases=dict(A='A',X='Q',VPWR='VDD',VPB='VDD',VGND='0',VNB='0',**{'a_114_74#':'MID'})
            if any(p not in aliases for p in ports):
                raise ValueError('all buffer ports explicitly bound')
            columns=['v(a)','i(vin)','v(q)','v(mid)','v(cref)','i(vcontrol)']
            init=directory/'.spiceinit';init.write_text('set ngbehavior=hsa\n')
            deck.write_text('\n'.join(['* Prospective periodic charge holdout',f'.lib "{pdk}" {corner}',
                f'.include "{model}"','.temp 27','.option reltol=1e-6 abstol=1e-12 num_threads=1',
                'VDD VDD 0 1.8',f'VIN A 0 {waveform}',f'XCELL '+' '.join(aliases[p] for p in ports)+' sky130_fd_sc_hs__clkbuf_16',
                'CQ Q 0 200f',f'VCONTROL CREF 0 {waveform}','CCONTROL CREF 0 20f',
                '.control','set wr_singlescale','set wr_vecnames','set numdgt=15','tran 1p 34n 0 1p',
                f'wrdata {data} '+' '.join(columns),'quit','.endc','.end'])+'\n')
            pins.update({str(p):sha(p) for p in (deck,init)})
            save(output/'status.json',dict(state='native_periodic_charge_validation_running',corner=corner,release_ready=False))
            with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+86400):
                previous=Path.cwd()
                try:
                    os.chdir(directory)
                    execute([ng,'-b',deck],directory/'native.log',time.clock_gettime(time.CLOCK_BOOTTIME)+3600,4)
                finally:
                    os.chdir(previous)
            if [v.lower() for v in data.open().readline().split()]!=['time',*columns]:
                raise ValueError('exact periodic current columns required')
            x=np.loadtxt(data,skiprows=1);t=x[:,0]
            if (x.ndim!=2 or x.shape[1]!=7 or not np.isfinite(x).all() or t[0]!=0
                    or abs(t[-1]-34e-9)>1e-15 or not np.all(np.diff(t)>0)):
                raise ValueError('complete finite periodic waveform required')
            controls=[];response=[]
            for k in range(2,10):
                rise,fall=(5+2.5*k)*1e-9,(6.25+2.5*k)*1e-9
                controls.extend([-integral(t,x[:,-1],rise-30e-12,rise+30e-12)/1.08,
                                  integral(t,x[:,-1],fall-30e-12,fall+30e-12)/1.08])
                high=(t>=rise+.8e-9)&(t<=rise+1e-9)
                low=(t>=rise+2.05e-9)&(t<=rise+2.25e-9)
                response.append(bool(np.any(high) and np.any(low) and np.all(x[high,3]>=1.62) and np.all(x[low,3]<=.18)))
            if any(abs(v/20e-15-1)>1e-4 for v in controls):
                raise ValueError('periodic reference capacitor control failed')
            measured=intrinsic_charge(t,x[:,1],x[:,2],x[:,3],x[:,4],caps)
            s=surfaces['corners'][corner]
            coefficients=np.array([*s['input_capacitances_fF'],s['Miller_capacitance_fF']])
            predicted=features(x[:,1],x[:,4])@coefficients
            observed=(t>=9e-9)&(t<=30e-9)
            residual=predicted[observed]-measured[observed]
            swing=float(np.ptp(measured[observed]))
            if swing<=0:
                raise ValueError('nonzero observed periodic charge swing required')
            results.append(dict(corner=corner,all_periodic_reference_controls_pass=True,
                all_periodic_output_levels_pass=all(response),maximum_charge_error_fC=float(np.max(np.abs(residual))),
                RMS_charge_error_fC=float(np.sqrt(np.mean(residual**2))),
                maximum_error_relative_to_charge_swing=float(np.max(np.abs(residual))/swing),
                internal_voltage_observed_not_predicted=True))
            artifacts.update({str(p):sha(p) for p in (data,directory/'native.log')})
        detail=output/'observations.json';save(detail,results);artifacts[str(detail)]=sha(detail)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,corners=results,
             independently_measured_periodic_holdout=True,coefficients_refitted=False,
             maximum_error_relative_to_charge_swing=max(r['maximum_error_relative_to_charge_swing'] for r in results),
             causal_internal_voltage_model_available=False,clock_receiver_model_qualified=False,
             full_flat_C_stitching_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='periodic_charge_holdout_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    run()
