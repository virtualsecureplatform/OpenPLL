"""Sample current MOS small-signal gate/drain response at one explicit bias."""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute

def numeric(path,columns):
    rows=[]
    for line in path.read_text().splitlines():
        try:values=[float(v)for v in line.split()]
        except ValueError:continue
        if not values:continue
        if len(values)!=columns or not all(math.isfinite(v)for v in values):raise ValueError('invalid AC current table')
        rows.append(values)
    if len(rows)!=2:raise ValueError('two requested frequency rows required')
    return rows

def run(output):
    base=ROOT/'build/signoff400';dc=base/'selected_keeper_current_primitive_DC_1287';receipt=dc/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['all_five_corner_native_DC_comparisons_complete']:raise ValueError('complete literal-geometry DC lineage required')
    geometry=dc/'geometries.json';rows=[g for g in json.loads(geometry.read_text())if g['kind']=='MOS']
    if len(rows)!=429:raise ValueError('all current MOS geometries required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));xy=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';ng=ROOT/'build/tools/ngspice47_diode_charge_fix_001/ngspice';lib='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    pins={**r['input_sha256'],**{str(p):sha(p)for p in [receipt,geometry,xy,ng,Path(__file__).resolve()]}};jobs=[]
    for corner in ['tt','ff','ss','sf','fs']:
        for excited in ['gate','drain']:
            folder=output/(corner+'_'+excited);folder.mkdir();decks={}
            for engine in ['ng','xy']:
                lines=[f'* All current MOS geometries, {corner}, {excited} AC excitation',f'.lib "{lib}" {corner}','VDD VPWR 0 1.8']
                currents=[]
                for i,g in enumerate(rows):
                    source='VPWR'if g['model'].startswith('sky130_fd_pr__pfet')else'0'
                    lines.extend([' '.join([f'Xtest{i}',f'D{i}',f'G{i}',source,source,g['model'],*g['parameters']]),f'Vgate{i} G{i} 0 DC .9 AC {int(excited=="gate")}',f'Vdrain{i} D{i} 0 DC .9 AC {int(excited=="drain")}'])
                    currents.extend([f'I(Vgate{i})',f'I(Vdrain{i})'])
                if engine=='ng':lines.extend(['.option klu reltol=1e-5 abstol=1e-9','.temp 27','.control','set num_threads=1','set numdgt=17','set wr_singlescale','set wr_vecnames','ac lin 2 25e6 400e6','wrdata '+str(folder/'reference.tsv')+' '+' '.join(currents),'quit','.endc','.end'])
                else:lines.extend(['.options parser model_binning=true','.options device temp=27','.options nonlin reltol=1e-5 abstol=1e-9','.ac lin 2 25e6 400e6','.print ac precision=17 '+' '.join(currents),'.end'])
                deck=folder/(engine+'.spice');deck.write_text('\n'.join(lines)+'\n');pins[str(deck)]=sha(deck);decks[engine]=deck
            jobs.append((corner,excited,folder,decks))
    verify(pins);save(output/'inputs.json',dict(input_sha256=pins,corners=['tt','ff','ss','sf','fs'],unique_MOS_parameter_sets=429,gate_DC_V=.9,drain_DC_V=.9,temperature_C=27,frequencies_Hz=[25e6,400e6],separate_gate_and_drain_AC_excitations_V=1,CPU=28,memory_GiB=4,native_cap_s=900,maximum_native_cases=20,automatic_identical_retry=False,release_ready=False));results=[];artifacts={}
    try:
        with lease(1,4,deadline):
            for corner,excited,folder,decks in jobs:
                save(output/'status.json',dict(state='comparing_current_primitive_AC',corner=corner,excited_terminal=excited,release_ready=False))
                for engine,binary,args in [('ng',ng,['-b']),('xy',xy,['-linsolv','umfpack_reuse','-o',folder/'candidate'])]:
                    verify({str(decks[engine]):pins[str(decks[engine])],str(binary):pins[str(binary)]});execute([binary,*args,decks[engine]],folder/(engine+'.log'),deadline,4)
                nr=numeric(folder/'reference.tsv',1+4*len(rows));xr=numeric(folder/'candidate.FD.prn',2+4*len(rows));measurements=[]
                for frequency,a,b in zip([25e6,400e6],nr,xr):
                    if abs(a[0]/frequency-1)>1e-12 or abs(b[1]/frequency-1)>1e-12:raise ValueError('frequency alignment mismatch')
                    for i in range(len(rows)):
                        for terminal,offset in [('gate',0),('drain',2)]:
                            j=4*i+offset;ref=complex(a[1+j],a[2+j]);candidate=complex(b[2+j],b[3+j]);measurements.append(dict(geometry=i,observed_terminal=terminal,frequency_Hz=frequency,reference_real_A=ref.real,reference_imag_A=ref.imag,candidate_real_A=candidate.real,candidate_imag_A=candidate.imag,complex_current_relative_error=abs(candidate-ref)/max(abs(ref),1e-18),reactive_current_difference_equivalent_F=abs(candidate.imag-ref.imag)/(2*math.pi*frequency)))
                detail=folder/'comparisons.json';save(detail,measurements);results.append(dict(corner=corner,excited_terminal=excited,observations=len(measurements),maximum_complex_current_relative_error=max(m['complex_current_relative_error']for m in measurements),maximum_reactive_difference_equivalent_fF=1e15*max(m['reactive_current_difference_equivalent_F']for m in measurements)))
                artifacts.update({str(p):sha(p)for p in [folder/'reference.tsv',folder/'candidate.FD.prn',folder/'ng.log',folder/'xy.log',detail]});save(output/'progress.json',results)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_twenty_native_AC_analyses_complete=True,unique_MOS_parameter_sets=429,gate_DC_V=.9,drain_DC_V=.9,temperature_C=27,frequencies_Hz=[25e6,400e6],complex_current_relative_error_floor_A=1e-18,full_bias_range_covered=False,transient_qualified=False,small_signal_model_qualified=False,full_PLL_model_qualified=False,release_ready=False));save(output/'status.json',dict(state='current_primitive_midpoint_AC_comparisons_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),automatic_identical_retry=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
