"""Evaluate the foundry generic-poly law explicitly and verify native responses."""
import argparse,json,os,sys,time,math,re
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from model_preparation_fast import model_closure
from probe_native_junction_alias_v2 import table
from check_current_generic_poly_models_v3 import numeric

MODEL='sky130_fd_pr__res_generic_po'


def work(out,deadline):
    reference=ROOT/'build/signoff400/startup_timing_current_generic_poly_models_003';receipt=reference/'assessment.json';a=json.loads(receipt.read_text());pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A');library=pdk/'libs.tech/ngspice/sky130.lib.spice';model_file=pdk/'libs.tech/ngspice/sky130_fd_pr__model__r+c.model.spice';monte=pdk/'libs.tech/ngspice/r+c.mrp1monte.spice';ng=ROOT/'build/tools/ngspice47/install/bin/ngspice';xyce=Path('/opt/xyce/bin/Xyce');spec_path=ROOT/'verification/signoff400/requirements.json';spec=json.loads(spec_path.read_text());devices=reference/'terminal_bindings.jsonl';paths=[receipt,devices,reference/'current_generic_poly_devices.spice',spec_path,monte,ng,xyce,ROOT/'build/apptainer/openpll-release-modern.sif',Path(__file__).resolve(),Path(__file__).with_name('model_preparation_fast.py'),Path(__file__).with_name('check_current_generic_poly_models_v3.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py'),*model_closure(library,deadline)];pins={str(p):sha(p) for p in paths}
    for p in (devices,reference/'current_generic_poly_devices.spice'):
        if pins[str(p)]!=a['artifacts'][str(p)]:raise ValueError('current resistor binding changed')
    for p in (ng,xyce,model_file):
        if pins[str(p)]!=a['input_sha256'][str(p)]:raise ValueError('reference simulator or foundry model changed')
    model=[l for l in model_file.read_text().splitlines() if l.lower().startswith('.model '+MODEL+' ')];mt=monte.read_text()
    if len(model)!=1 or not all(token in model[0] for token in ('tc1r=tc1rsgpu','tc2r=tc2rsgpu','rsh=rp1','-tol_poly/2-poly_dw/2','tnom=30')):raise ValueError('exact supported PDK model law')
    if 'r_tot = {(rp1+rp1_mm)*l/(w-1e6*(-tol_poly-poly_dw))+r}' not in mt or '.model sky130_fd_pr__res_generic_po__monte r tref = 30.0' not in mt:raise ValueError('independent foundry scalar-wrapper law differs')
    # No mismatch variables or arbitrary sheet default are introduced.
    bindings=[json.loads(l) for l in devices.read_text().splitlines()];geometries=sorted({(r['native_parameters']['w'],r['native_parameters']['l']) for r in bindings})
    if len(bindings)!=24 or geometries!=[('0.48','0.5'),('0.51','0.045')]:raise ValueError('exact current resistor geometry set')
    fragment=out/'current_generic_poly_devices.spice';fragment.write_text('* Select exactly one matching fixed-PVT model definition file.\n'+'\n'.join(' '.join([r['instance'],*r['emitted_nodes'],'openpll_checked_poly_g'+str(geometries.index((r['native_parameters']['w'],r['native_parameters']['l'])))]) for r in bindings)+'\n');artifacts=[fragment];results=[]
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for corner in spec['corners']:
        for temperature in spec['temperatures_c']:
            where=out/f'{corner}_{temperature}';where.mkdir();deck=where/'parameters.cir';values=where/'parameters.dat';deck.write_text('\n'.join(['* Evaluate original PDK parameters without a translated resistor.',f'.lib "{library}" {corner}',f'.temp {temperature}','BRSH p_rsh 0 V={rp1}','BDW p_dw 0 V={-tol_poly-poly_dw}','BTC1 p_tc1 0 V={tc1rsgpu}','BTC2 p_tc2 0 V={tc2rsgpu}','BMM p_mm 0 V={MC_MM_SWITCH}', '.control','set wr_singlescale','set wr_vecnames','set numdgt=17','op',f'wrdata {values} v(p_rsh) v(p_dw) v(p_tc1) v(p_tc2) v(p_mm)','quit','.endc','.end'])+'\n');execute([ng,'-b',deck],where/'parameters.log',deadline,4);raw=numeric(values,6,1)[0];rsh,dw,tc1,tc2,mm=raw[-5:]
            if rsh<=0 or mm!=0 or not all(map(math.isfinite,(rsh,dw,tc1,tc2))):raise ValueError('positive deterministic PDK law required')
            dt=temperature-30;factor=1+tc1*dt+tc2*dt*dt
            if factor<=0:raise ValueError('positive fixed-temperature resistance factor')
            resistances=[];definitions=['* Explicit deterministic PDK generic-poly law at '+corner+' '+str(temperature)+' C.']
            for i,(w,l) in enumerate(geometries):
                effective_width=float(w)-1e6*dw
                if effective_width<=0:raise ValueError('positive effective poly width')
                value=rsh*float(l)/effective_width*factor;resistances.append(value);definitions.extend([f'.subckt openpll_checked_poly_g{i} t1 t2',f'R0 t1 t2 {value:.17g}',f'.ends openpll_checked_poly_g{i}'])
            model_view=out/f'poly_models_{corner}_{temperature}C.spice';model_view.write_text('\n'.join(definitions)+'\n');pins[str(model_view)]=sha(model_view);artifacts.extend([model_view,deck,values,where/'parameters.log']);native={}
            for analysis in ('dc','ac'):
                probe=where/(analysis+'.cir');quantities='V(ctrl) I(VG0) I(VG1)' if analysis=='dc' else 'IR(VG0) II(VG0) IR(VG1) II(VG1)';lines=['* Checked scalar-poly native comparison.',f'.include "{model_view}"',f'.options device temp={temperature}', '.options nonlin reltol=1e-10 abstol=1e-20','Vdrive ctrl 0 DC 0 AC 1','VG0 n0 ctrl 0','VG1 n1 ctrl 0','XTEST0 n0 0 openpll_checked_poly_g0','XTEST1 n1 0 openpll_checked_poly_g1','.dc Vdrive 0 1.8 0.3' if analysis=='dc' else '.ac lin 2 1e6 4e8',f'.print {analysis} precision=16 '+quantities,'.end'];probe.write_text('\n'.join(lines)+'\n');execute([xyce,'-linsolv','KLU','-quiet','-o',probe,probe],where/(analysis+'.log'),deadline,4);wave=Path(str(probe)+('.prn' if analysis=='dc' else '.FD.prn'));native[analysis]=table(wave,2 if analysis=='dc' else 4,7 if analysis=='dc' else 2);artifacts.extend([probe,wave,where/(analysis+'.log')])
            ngdc=reference/where.name/'ng_dc.dat';ngac=reference/where.name/'ng_ac.dat'
            for p in (ngdc,ngac):
                pins[str(p)]=sha(p)
                if pins[str(p)]!=a['artifacts'][str(p)]:raise ValueError('native reference waveform changed')
            dc=numeric(ngdc,4,7);ac=[r for r in numeric(ngac,5,0) if any(abs(r[0]/f-1)<1e-12 for f in (1e6,4e8))]
            if len(ac)!=2:raise ValueError('complete reference AC frequencies')
            maximum=maximum_abs=0;matched=True;ratios=[]
            for left,right in zip(dc,native['dc'],strict=True):
                if abs(left[1]-right[1])>1e-12:raise ValueError('same DC sweep')
                for i in range(2):
                    d=abs(left[2+i]-right[2+i]);scale=max(abs(left[2+i]),abs(right[2+i]),1e-18);maximum=max(maximum,d/scale);maximum_abs=max(maximum_abs,d);matched&=d<=1e-15+1e-10*scale
                if left[1]>1.7:ratios=[(-left[1]/left[2+i])/resistances[i] for i in range(2)]
            for left,right in zip(ac,native['ac'],strict=True):
                if abs(left[0]/right[1]-1)>1e-12:raise ValueError('same AC frequencies')
                for i in range(2):
                    n=complex(left[1+2*i],left[2+2*i]);x=complex(right[2+2*i],right[3+2*i]);d=abs(n-x);scale=max(abs(n),abs(x),1e-18);maximum=max(maximum,d/scale);maximum_abs=max(maximum_abs,d);matched&=d<=1e-15+1e-10*scale
            if len(ratios)!=2:raise ValueError('DC geometry control missing')
            result=dict(corner=corner,required_global_temperature_c=temperature,PDK_parameters=dict(rsh_ohms_per_square=rsh,width_reduction_m=dw,tc1_per_C=tc1,tc2_per_C2=tc2,tnom_C=30,MC_MM_SWITCH=mm),evaluated_resistances_ohm=resistances,reference_measured_over_analytic_resistance_ratios=ratios,maximum_scaled_current_difference=maximum,maximum_absolute_current_difference_A=maximum_abs,diagnostic_numeric_screen_pass=matched,model_definitions=str(model_view));results.append(result);save(where/'result.json',result);artifacts.append(where/'result.json');save(out/'status.json',dict(state='checked_poly_translation_controls_running',completed_points=len(results),required_points=15,release_qualified=False))
    if any(sha(p)!=h for p,h in pins.items()):raise ValueError('poly translation source changed')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},results=results,current_resistors=24,current_geometries=geometries,all_native_instance_names_and_constrained_nodes_preserved=True,original_PDk_generic_poly_comparison_preserved=True,model_law='rp1*l/(w-1e6*(-tol_poly-poly_dw)) * (1+tc1rsgpu*(T-30)+tc2rsgpu*(T-30)^2)',source_PDk_width_and_temperature_law_verified=True,all_15_corrected_native_PVT_controls_terminal=True,all_numeric_screens_pass=all(r['diagnostic_numeric_screen_pass'] for r in results),maximum_scaled_current_difference=max(r['maximum_scaled_current_difference'] for r in results),model_compatibility_support_prepared=all(r['diagnostic_numeric_screen_pass'] for r in results),fixed_temperature_models_require_matching_selected_corner_temperature=True,Monte_Carlo_model_supported=False,numeric_screen_is_physical_error_budget=False,physical_response_error_enclosure_qualified=False,full_physical_PLL_model_integrated=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False));save(out/'status.json',dict(state='checked_poly_translation_controls_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--inside',action='store_true');p.add_argument('--deadline',type=float);args=p.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.deadline)
    out.mkdir(parents=True,exist_ok=False);producer=ROOT/'build/signoff400/startup_timing_current_generic_poly_models_003';owner=json.loads((producer/'owner.json').read_text());deadline=owner['deadline_uptime']+10800;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=owner['pid'],producer_birth=owner['birth'],deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_exact_original_poly_comparison',release_qualified=False))
    try:
        while not (producer/'assessment.json').exists():
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=owner['deadline_uptime'] or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original poly comparison stopped without assessment')
            time.sleep(2)
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise

if __name__=='__main__':main()
