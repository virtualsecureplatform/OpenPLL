"""Compare two unchanged keeper RC attachment diagnostics in native Xyce."""
import argparse,json,os,re,sys,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from prototype_native_literal_templates import factor
from prototype_xyce_resistor_translation import translate as resistor
from capture_selected_native_runtime import closure
from assess_selected_detector_phase_probe_v2 import read_selected
from assess_selected_isolated_control import frequency


def capacitors(text):return [line for line in text.splitlines()if line.split()and line.split()[0].startswith('Cflat')]


def run(models,output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{20});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        receipt=models/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if not a['ideal_supply_passivity_certified']or not a['zero_wire_R_exact_device_topology_and_C_operator_match']or a['SPEF_capacitance_added']:
            raise ValueError('complete passive nonduplicated RC models required')
        library='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
        pdk_pins,edges=closure(os.getpid(),library)
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';folder=Path(__file__).resolve().parent
        files=[receipt,binary,Path(__file__).resolve(),*[folder/n for n in ['prototype_native_literal_templates.py','prototype_xyce_resistor_translation.py','capture_selected_native_runtime.py','assess_selected_detector_phase_probe_v2.py','assess_selected_isolated_control.py']]]
        plans=[]
        for attachment in ['driver','farthest']:
            source=models/('nom_'+attachment+'.spice');original=source.read_text();caps=capacitors(original)
            stripped='\n'.join(line for line in original.splitlines()if line not in set(caps))+'\n'
            factored,metrics=factor(stripped);end=[line for line in factored.splitlines()if line.startswith('.ends ')][-1]
            factored=factored.replace(end,'\n'.join(caps)+'\n'+end)
            adapted,count=resistor(factored)
            if capacitors(adapted)!=caps:raise ValueError('capacitor cards changed')
            case=output/attachment;case.mkdir();model=case/'model.spice';model.write_text(adapted)
            top=next(line.split()[1]for line in original.splitlines()if line.startswith('.subckt '))
            ports=next(line.split()[2:]for line in original.splitlines()if line.startswith('.subckt '))
            controls=['VVPWR VPWR 0 1.8','VVPB VPB 0 1.8','VVGND VGND 0 0','VVNB VNB 0 0',
                      'VRESET RESET_N 0 PULSE(0 1.8 5n 50p 50p 80n 160n)']
            for pin in ports:
                m=re.fullmatch(r'DCO_THERM\[(\d+)\]',pin)
                if m:controls.append(f'Vfine{m[1]} {pin} 0 '+('0'if int(m[1])<112 else '1.8'));continue
                m=re.fullmatch(r'COARSETHERMAL_CODE\[(\d+)\]',pin)
                if m:controls.append(f'Vcoarse{m[1]} {pin} 0 '+('1.8'if int(m[1])<20 else '0'));continue
                if pin not in ['VGND','VNB','VPWR','VPB','RESET_N','PLLOUT']:raise ValueError('unbound external pin '+pin)
            deck=case/'control.spice';raw=case/'control.raw'
            deck.write_text('* Native isolated keeper RC attachment diagnostic\n'+f'.lib "{library}" tt\n.include "{model}"\n'+ '\n'.join(controls)+'\nXDUT '+' '.join(ports)+' '+top+f'\n.options parser model_binning=true\n.options device temp=27\n.options nonlin reltol=1e-5 abstol=1e-9\n.options timeint reltol=1e-5 abstol=1e-9\n.tran 10p 80n 0 10p\n.print tran format=raw precision=17 file={raw} v(PLLOUT)\n.end\n')
            files.extend([source,model,deck]);plans.append(dict(attachment=attachment,folder=case,deck=deck,raw=raw,literal_templates=metrics,poly_adapter_templates=count))
        pins={**pdk_pins,**{str(p):sha(p)for p in files}};verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,PDK_include_edges=edges,operating_point=dict(corner='tt',temperature_c=27,supply_v=1.8),coarse=20,fine=112,thermometer_inverted=True,reset_release_ns=5,simulation_time_ns=80,maximum_step_ps=10,CPU=20,memory_GiB=12,native_cap_s_per_case=10800,max_native_cases=2,automatic_identical_retry=False,parent_loading_complete=False,release_ready=False))
        results=[]
        for plan in plans:
            verify(pins);case=plan['folder'];save(output/'status.json',dict(state='keeper_attachment_native_running',attachment=plan['attachment'],release_ready=False))
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800;start=time.monotonic()
            with lease(1,12,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',plan['deck']],case/'native.log',deadline,12)
            verify(pins);data=read_selected(plan['raw'],{'output':'PLLOUT'},80e-9)
            windows=[dict(window_ns=[lo,hi],frequency=frequency(data,lo,hi))for lo,hi in [(20,40),(40,55),(60,79)]]
            result=dict(attachment=plan['attachment'],elapsed_s=time.monotonic()-start,normal_native_completion=True,windows=windows)
            save(case/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [plan['raw'],case/'native.log']},**result,release_ready=False));results.append(result)
            save(output/'completed_cases.json',results)
        save(output/'assessment.json',dict(input_sha256=pins,results=results,both_native_cases_completed_normally=True,attachment_uncertainty_bounded=False,parent_loading_complete=False,model_family_qualified=False,selected=False,release_ready=False))
        save(output/'status.json',dict(state='keeper_attachment_pair_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--models',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.models.resolve(),a.output.resolve())
