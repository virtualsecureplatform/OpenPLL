"""Bind current generic-poly resistors and compare direct PDK DC/AC responses."""
import argparse,json,os,sys,time,math,re
from pathlib import Path
from collections import Counter
from decimal import Decimal
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute
from model_preparation_fast import model_closure
from probe_native_junction_alias_v2 import table

MODEL='sky130_fd_pr__res_generic_po'


def numeric(path,columns,rows):
    lines=path.read_text().splitlines()
    if not lines:raise ValueError('native reference output missing')
    data=[[float(v) for v in line.split()] for line in lines[1:] if line.strip()]
    if len(data)!=rows or any(len(row)!=columns or not all(map(math.isfinite,row)) for row in data):raise ValueError('reference output shape or finiteness')
    return data


def work(out,deadline):
    base=ROOT/'build/signoff400';provenance=base/'startup_timing_native_device_provenance_001/assessment.json';p=json.loads(provenance.read_text());ledger=provenance.parent/'native_device_provenance.jsonl';spec_path=ROOT/'verification/signoff400/requirements.json';spec=json.loads(spec_path.read_text());xyce=Path('/opt/xyce/bin/Xyce');ngspice=ROOT/'build/tools/ngspice47/install/bin/ngspice';ng_proof=ngspice.parents[2]/'binary_provenance.json';checked=ROOT/'build/timing400/release_001/hs_diode_geometry_comparison_001/assessment.json';old=json.loads(checked.read_text());image=ROOT/'build/apptainer/openpll-release-modern.sif';pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A');library=pdk/'libs.tech/ngspice/sky130.lib.spice';model_file=pdk/'libs.tech/ngspice/sky130_fd_pr__model__r+c.model.spice'
    paths=[provenance,ledger,spec_path,xyce,ngspice,ng_proof,checked,image,Path(__file__).resolve(),Path(__file__).with_name('model_preparation_fast.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py'),*model_closure(library,deadline)];pins={str(x):sha(x) for x in paths}
    if pins[str(ledger)]!=p['artifacts'][str(ledger)] or pins[str(ngspice)]!=old['input_sha256'][str(ngspice)] or pins[str(ng_proof)]!=old['input_sha256'][str(ng_proof)]:raise ValueError('native device or reference binary provenance changed')
    text=model_file.read_text();blocks=re.findall(r'(?im)^\.subckt\s+'+MODEL+r'\s+([^\n]+)\n(.*?)^\.ends[^\n]*$',text,re.S)
    if len(blocks)!=1 or blocks[0][0].split()!=['t1','t2','w=1','l=1']:raise ValueError('exact generic-poly wrapper contract')
    cards=[s.strip() for s in blocks[0][1].splitlines() if s.strip() and not s.lstrip().startswith('*')]
    if cards!=['R0 t1 t2 sky130_fd_pr__res_generic_po w = {w} l = {l}']:raise ValueError('one foundry resistor, without charge elements, required')
    model_cards=[s for s in text.splitlines() if s.lower().startswith('.model '+MODEL+' ')]
    if len(model_cards)!=1 or model_cards[0].split()[2].lower()!='r':raise ValueError('unique generic-poly R model')
    if re.search(r'\b(c|cap|cj|cjsw)\s*=',model_cards[0],re.I):raise ValueError('unexpected intrinsic charge parameter')
    devices=[]
    with ledger.open('rb') as f:
        for line in f:
            if ('"model": "'+MODEL+'"').encode() in line:devices.append(json.loads(line))
    if len(devices)!=24:raise ValueError('all 24 current generic-poly devices required')
    geometries=Counter();lines=['* Current generic-poly devices; caller supplies checked PDK corner and temperature.'];bindings=[]
    for device in devices:
        if device['pre_R_parameters']!=device['post_R_parameters'] or set(device['post_R_parameters'])!={'w','l'} or device['unresolved_parameter_differences']:raise ValueError('exact unchanged current resistor geometry')
        params=device['post_R_parameters'];geometry=(params['w'],params['l']);geometries[geometry]+=1;terminals=device['terminal_bindings']
        if device['native_terminal_order']!=[2,3] or [b['native_terminal_enum'] for b in terminals]!=[2,3]:raise ValueError('audited source/drain order')
        if terminals[0]['constrained_voltage_id']==terminals[1]['constrained_voltage_id']:raise ValueError('finite resistor collapsed by voltage map')
        length,width=device['native_trace_geometry'][-2:]
        if Decimal(params['w'])*200!=width or Decimal(params['l'])*200!=length:raise ValueError('native length/width geometry encoding')
        nodes=['_v'+str(b['constrained_voltage_id']) for b in terminals];lines.append(' '.join([device['instance'],*nodes,MODEL,*[k+'='+v for k,v in params.items()]]));bindings.append(dict(instance=device['instance'],point_internal=device['point_internal'],native_parameters=params,emitted_nodes=nodes,terminal_bindings=terminals))
    if geometries!={('0.51','0.045'):20,('0.48','0.5'):4}:raise ValueError('current supported geometry inventory')
    fragment=out/'current_generic_poly_devices.spice';fragment.write_text('\n'.join(lines)+'\n');mapping=out/'terminal_bindings.jsonl';mapping.write_text(''.join(json.dumps(r)+'\n' for r in bindings));geometry_order=sorted(geometries);results=[];artifacts=[fragment,mapping]
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for corner in spec['corners']:
        for temperature in spec['temperatures_c']:
            where=out/f'{corner}_{temperature}';where.mkdir();common=[f'.lib "{library}" {corner}','Vdrive ctrl 0 0']
            for i,(w,l) in enumerate(geometry_order):common.extend([f'VG{i} n{i} ctrl 0',f'XR{i} n{i} 0 {MODEL} w={w} l={l}'])
            # ngspice writes unambiguous full-precision vectors, avoiding paged print tables.
            ng=where/'ngspice.cir';ng.write_text('\n'.join(['* Direct foundry generic-poly reference.',*common,f'.temp {temperature}', '.options reltol=1e-10 abstol=1e-20 gmin=1e-18','.control','set wr_singlescale','set wr_vecnames','set numdgt=17','dc Vdrive 0 1.8 0.3',f'wrdata {where}/ng_dc.dat v(ctrl) i(VG0) i(VG1)','ac lin 2 1e6 4e8',f'wrdata {where}/ng_ac.dat real(i(VG0)) imag(i(VG0)) real(i(VG1)) imag(i(VG1))','quit','.endc','.end'])+'\n')
            # Apply unit AC excitation through the existing drive source.
            ng.write_text(ng.read_text().replace('Vdrive ctrl 0 0','Vdrive ctrl 0 DC 0 AC 1'))
            execute([ngspice,'-b',ng],where/'ngspice.log',deadline,4);reference_dc=numeric(where/'ng_dc.dat',4,7);reference_ac=numeric(where/'ng_ac.dat',5,2);artifacts.extend([ng,where/'ngspice.log',where/'ng_dc.dat',where/'ng_ac.dat']);observed={}
            for analysis in ('dc','ac'):
                deck=where/('xyce_'+analysis+'.cir');quantities='V(ctrl) I(VG0) I(VG1)' if analysis=='dc' else 'IR(VG0) II(VG0) IR(VG1) II(VG1)';deck.write_text('\n'.join(['* Direct foundry generic-poly native control.',*[s.replace('Vdrive ctrl 0 0','Vdrive ctrl 0 DC 0 AC 1') for s in common],f'.options device temp={temperature} gmin=1e-18','.options nonlin reltol=1e-10 abstol=1e-20','.dc Vdrive 0 1.8 0.3' if analysis=='dc' else '.ac lin 2 1e6 4e8',f'.print {analysis} precision=16 '+quantities,'.end'])+'\n');execute([xyce,'-linsolv','KLU','-quiet','-o',deck,deck],where/('xyce_'+analysis+'.log'),deadline,4);wave=Path(str(deck)+('.prn' if analysis=='dc' else '.FD.prn'));observed[analysis]=table(wave,2 if analysis=='dc' else 4,7 if analysis=='dc' else 2);artifacts.extend([deck,wave,where/('xyce_'+analysis+'.log')])
            max_abs=max_rel=0;resistances=[];matched=True
            for ngrow,xyrow in zip(reference_dc,observed['dc'],strict=True):
                if abs(ngrow[0]-ngrow[1])>1e-12 or abs(ngrow[1]-xyrow[1])>1e-12:raise ValueError('aligned DC sweep required')
                for i in range(2):
                    left,right=ngrow[2+i],xyrow[2+i];difference=abs(left-right);max_abs=max(max_abs,difference);max_rel=max(max_rel,difference/max(abs(left),abs(right),1e-18));matched&=difference<=1e-15+1e-10*max(abs(left),abs(right))
                if ngrow[1]>1.7:
                    resistances=[dict(width_um=w,length_um=l,ngspice_measured_ohms=-ngrow[1]/ngrow[2+i],xyce_measured_ohms=-xyrow[1]/xyrow[2+i]) for i,(w,l) in enumerate(geometry_order)]
            for ngrow,xyrow in zip(reference_ac,observed['ac'],strict=True):
                if abs(ngrow[0]/xyrow[1]-1)>1e-12:raise ValueError('aligned AC frequency required')
                for i in range(2):
                    left=complex(ngrow[1+2*i],ngrow[2+2*i]);right=complex(xyrow[2+2*i],xyrow[3+2*i]);difference=abs(left-right);max_abs=max(max_abs,difference);max_rel=max(max_rel,difference/max(abs(left),abs(right),1e-18));matched&=difference<=1e-15+1e-10*max(abs(left),abs(right))
            if len(resistances)!=2 or any(not (r['ngspice_measured_ohms']>0 and r['xyce_measured_ohms']>0) for r in resistances):raise ValueError('finite positive measured resistances required')
            result=dict(corner=corner,temperature_c=temperature,resistances=resistances,maximum_absolute_current_difference_a=max_abs,maximum_scaled_current_difference=max_rel,diagnostic_cross_simulator_numeric_screen_pass=matched);results.append(result);save(where/'result.json',result);artifacts.append(where/'result.json');save(out/'status.json',dict(state='generic_poly_PVT_comparison_running',completed_points=len(results),required_points=15,release_qualified=False))
    if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('current poly model/binary input changed')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in artifacts},current_native_poly_resistors=24,geometry_counts=[dict(width_um=w,length_um=l,instances=n) for (w,l),n in geometries.items()],all_parameters_and_native_terminal_order_preserved=True,PDK_wrapper_contains_one_resistor_and_no_charge_elements=True,all_15_native_and_reference_PVT_analyses_terminal=True,results=results,diagnostic_cross_simulator_numeric_screen=dict(absolute_A=1e-15,relative=1e-10,is_physical_acceptance_budget=False),all_diagnostic_numeric_screens_pass=all(r['diagnostic_cross_simulator_numeric_screen_pass'] for r in results),physical_response_error_enclosure_qualified=False,final_producer_node_maps_reconciled=False,full_physical_PLL_model_integrated=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False));save(out/'status.json',dict(state='current_generic_poly_model_comparison_complete',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--inside',action='store_true');p.add_argument('--deadline',type=float);args=p.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.deadline)
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=1,memory_GiB=4,deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resources',release_qualified=False))
    try:
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',out],out/'controller.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise

if __name__=='__main__':main()
