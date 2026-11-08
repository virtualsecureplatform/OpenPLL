"""Isolate omitted PBSWGD defaulting without the PDK or PLL netlist."""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute

def numbers(path,columns):
    result=[]
    for line in path.read_text().splitlines():
        try:row=list(map(float,line.split()))
        except ValueError:continue
        if not row:continue
        if len(row)!=columns or not all(math.isfinite(v)for v in row):raise ValueError('invalid minimal AC table')
        result.append(row)
    if len(result)!=3:raise ValueError('three complete AC frequencies required')
    return result

def run(output,xy):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+180
    ng=ROOT/'build/tools/ngspice47_diode_charge_fix_001/ngspice';pins={str(p):sha(p)for p in [xy,ng,Path(__file__).resolve()]};results=[];artifacts={}
    cases=[('omitted_distinct',.95578,None),('explicit_source_gate',.95578,.95578),('omitted_equal',.2,None),('explicit_asymmetric',.95578,.7)]
    cases=[(f'v{version}_'+name,source_gate,drain_gate,version)for version in ['4.6.1','4.7.0','4.8.2']for name,source_gate,drain_gate in cases]
    for name,source_gate,drain_gate,version in cases:
        folder=output/name;folder.mkdir();model=f'.model probe nmos level=54 version={version} permod=1 cjs=0 cjd=0 cjsws=0 cjswd=0 cjswgs=2.38232788e-10 pbsws=.2 pbswgs={source_gate} mjswgs=.8 mjswgd=.8 cgso=0 cgdo=0 cgbo=0 tnom=27'
        if drain_gate is not None:model+=f' pbswgd={drain_gate}'
        circuit='* Isolated omitted drain gate-sidewall junction potential\n'+model+'\nMtest drain gate 0 0 probe w=1u l=1u ad=0 as=0 pd=1u ps=1u\nVgate gate 0 DC 0 AC 0\nVdrain drain 0 DC .9 AC 1\n'
        decks={}
        for engine in ['ng','xy']:
            if engine=='ng':tail=f'.temp 27\n.control\nset numdgt=17\nset wr_singlescale\nset wr_vecnames\nac lin 3 25e6 400e6\nwrdata {folder/"reference.tsv"} i(vdrain)\nquit\n.endc\n.end\n'
            else:tail='.options device temp=27\n.ac lin 3 25e6 400e6\n.print ac precision=17 I(Vdrain)\n.end\n'
            deck=folder/(engine+'.spice');deck.write_text(circuit+tail);decks[engine]=deck;pins[str(deck)]=sha(deck)
        verify(pins)
        with lease(1,2,deadline):
            execute([ng,'-b',decks['ng']],folder/'ng.log',deadline,2)
            execute([xy,'-linsolv','umfpack_reuse','-o',folder/'candidate',decks['xy']],folder/'xy.log',deadline,2)
        n=numbers(folder/'reference.tsv',3);x=numbers(folder/'candidate.FD.prn',4);observations=[]
        for a,b in zip(n,x):
            if abs(a[0]/b[1]-1)>1e-12:raise ValueError('frequency mismatch')
            f=a[0];nc=-a[2]/(2*math.pi*f);xc=-b[3]/(2*math.pi*f);observations.append(dict(frequency_Hz=f,ngspice_reactive_cap_fF=nc*1e15,Xyce_reactive_cap_fF=xc*1e15,delta_fF=(xc-nc)*1e15))
        correct=source_gate if drain_gate is None else drain_gate;xy_expected=correct
        capacitance=lambda potential:2.38232788e-10*1e-6*(1+.9/potential)**(-.8)*1e15
        results.append(dict(case=name,PBSWGS=source_gate,PBSWGD=drain_gate,mathematical_ngspice_default_or_explicit_fF=capacitance(correct),mathematical_inspected_Xyce_default_or_explicit_fF=capacitance(xy_expected),observations=observations))
        artifacts.update({str(p):sha(p)for p in [folder/'reference.tsv',folder/'candidate.FD.prn',folder/'ng.log',folder/'xy.log']})
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,all_twentyfour_native_analyses_complete=True,results=results,PDK_used=False,temperature_C=27,versions_requested=['4.6.1','4.7.0','4.8.2'],scope='Minimal junction-defaulting control; not a full MOS or PLL qualification',selected_backend=str(xy),fix_native_validation_only=True,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--xyce',type=Path,required=True);a=p.parse_args();run(a.output.resolve(),a.xyce.resolve())
