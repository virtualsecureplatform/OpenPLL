"""Sample all current flat MOS/poly parameter sets against native ngspice at 27 C."""
import argparse,json,math,os,time
from decimal import Decimal
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from prototype_xyce_resistor_translation import DEFINITION

def geometries(text):
    result={}
    for line in text.splitlines():
        f=line.split()
        if not f or f[0]!='Xdevice':continue
        positions=[i for i,v in enumerate(f)if v.startswith('sky130_fd_pr__')]
        if positions==[5]:kind='MOS';j=5;model=f[j]
        elif len(f)>3 and f[3]=='__openpll_xyce_poly_resistor':kind='poly';j=3;model='sky130_fd_pr__res_generic_po'
        else:continue
        params=tuple(sorted((v.split('=')[0],Decimal(v.split('=')[1]))for v in f[j+1:]))
        key=(kind,model,params)
        result[key]=dict(kind=kind,model=model,parameters=f[j+1:])
    return list(result.values())

def table(path):
    lines=path.read_text().splitlines();header=lines[0].lower().split();rows=[]
    for line in lines[1:]:
        try:values=[float(v)for v in line.split()]
        except ValueError:continue
        if not values:continue
        if len(values)!=len(header) or not all(math.isfinite(v)for v in values):raise ValueError('invalid primitive current table')
        rows.append(values)
    if len(rows)!=3:raise ValueError('three complete bias rows required')
    return header,rows

def run(output):
    base=ROOT/'build/signoff400';model=base/'selected_keeper_flat_native_model_1208/model.spice';receipt=model.parent/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    smoke=base/'selected_keeper_flat_native_smoke_1210/assessment.json';s=json.loads(smoke.read_text());verify(s['input_sha256']);verify(s['artifacts'])
    rows=geometries(model.read_text())
    if sum(r['kind']=='MOS'for r in rows)!=429 or sum(r['kind']=='poly'for r in rows)!=2:raise ValueError('complete current geometry template inventory required')
    backend=smoke.parent/'backend_model.spice'
    if DEFINITION.strip()not in backend.read_text():raise ValueError('poly adapter differs from current backend')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));xy=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';ng=ROOT/'build/tools/ngspice47_diode_charge_fix_001/ngspice';lib='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    pins={**s['input_sha256'],**{str(p):sha(p)for p in [receipt,model,smoke,backend,xy,ng,Path(__file__).resolve(),Path(__file__).with_name('prototype_xyce_resistor_translation.py')]}}
    save(output/'geometries.json',rows);pins[str(output/'geometries.json')]=sha(output/'geometries.json');save(output/'inputs.json',dict(input_sha256=pins,corners=['tt','ff','ss','sf','fs'],temperature_C=27,gate_biases_V=[0,.9,1.8],drain_probe_biases_V=[.45,.9],unique_MOS_parameter_sets=429,unique_poly_parameter_sets=2,maximum_native_cases=10,CPU=28,memory_GiB=4,native_cap_s=1800,automatic_identical_retry=False,release_ready=False));results=[];artifacts={}
    try:
        with lease(1,4,deadline):
            for corner in ['tt','ff','ss','sf','fs']:
                folder=output/corner;folder.mkdir();decks={};probes=[]
                for engine in ['ng','xy']:
                    lines=[f'* Current literal primitive DC control, {corner}, 27 C',f'.lib "{lib}" {corner}','VDD VPWR 0 1.8','VIN VIN 0 0']
                    if engine=='xy':lines.append(DEFINITION)
                    for gi,g in enumerate(rows):
                        for vi,v in enumerate([.45,.9]):
                            i=2*gi+vi;source='VPWR'if g['model'].startswith('sky130_fd_pr__pfet')else'0';terminals=[f'P{i}','VIN',source,source]if g['kind']=='MOS'else[f'P{i}','0'];name='__openpll_xyce_poly_resistor'if engine=='xy'and g['kind']=='poly'else g['model'];lines.extend([' '.join([f'Xtest{i}',*terminals,name,*g['parameters']]),f'Vprobe{i} P{i} 0 {v}'])
                            if engine=='xy':probes.append(dict(index=i,geometry=gi,kind=g['kind'],probe_voltage_V=v))
                    if engine=='ng':lines.extend(['.option klu reltol=1e-5 abstol=1e-9','.temp 27','.control','set num_threads=1','set numdgt=17','set wr_singlescale','set wr_vecnames','dc VIN 0 1.8 0.9','wrdata '+str(folder/'reference.tsv')+' '+' '.join(f'i(vprobe{i})'for i in range(2*len(rows))),'quit','.endc','.end'])
                    else:lines.extend(['.options parser model_binning=true','.options device temp=27','.options nonlin reltol=1e-5 abstol=1e-9','.dc VIN 0 1.8 0.9','.print dc precision=17 V(VIN) '+' '.join(f'I(Vprobe{i})'for i in range(2*len(rows))),'.end'])
                    deck=folder/(engine+'.spice');deck.write_text('\n'.join(lines)+'\n');decks[engine]=deck;pins[str(deck)]=sha(deck)
                verify(pins);save(output/'status.json',dict(state='comparing_current_primitive_DC',corner=corner,release_ready=False))
                execute([ng,'-b',decks['ng']],folder/'ng.log',deadline,4);execute([xy,'-linsolv','umfpack_reuse','-o',folder/'candidate',decks['xy']],folder/'xy.log',deadline,4)
                nh,nr=table(folder/'reference.tsv');xh,xr=table(folder/'candidate.prn');measurements=[]
                for bi,(a,b)in enumerate(zip(nr,xr)):
                    if abs(a[0]-.9*bi)>1e-12 or abs(b[xh.index('v(vin)')]-.9*bi)>1e-12:raise ValueError('gate bias alignment mismatch')
                    for probe in probes:
                        index=probe['index'];ref=a[nh.index(f'i(vprobe{index})')];candidate=b[xh.index(f'i(vprobe{index})')];floor=1e-9 if probe['kind']=='MOS'else 1e-12
                        measurements.append(dict(**probe,gate_bias_V=.9*bi,ngspice_A=ref,Xyce_A=candidate,absolute_error_A=abs(ref-candidate),relative_error=abs(ref-candidate)/max(abs(ref),floor)))
                details=folder/'comparisons.json';save(details,measurements);m=[r for r in measurements if r['kind']=='MOS'];p=[r for r in measurements if r['kind']=='poly'];results.append(dict(corner=corner,MOS_max_relative_error_floor_1nA=max(r['relative_error']for r in m),poly_max_relative_error_floor_1pA=max(r['relative_error']for r in p),MOS_current_observations=len(m),poly_current_observations=len(p),poly_previous_1e10_relative_screen_pass=all(r['relative_error']<1e-10 for r in p)))
                artifacts.update({str(p):sha(p)for p in [folder/'reference.tsv',folder/'candidate.prn',folder/'ng.log',folder/'xy.log',details]});save(output/'progress.json',results)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_five_corner_native_DC_comparisons_complete=True,unique_MOS_parameter_sets=429,unique_poly_parameter_sets=2,MOS_relative_error_denominator_floor_A=1e-9,poly_relative_error_denominator_floor_A=1e-12,MOS_accuracy_qualified=False,poly_dynamic_and_noise_qualified=False,transient_qualified=False,full_PLL_model_qualified=False,release_ready=False));save(output/'status.json',dict(state='current_primitive_DC_comparisons_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),automatic_identical_retry=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
