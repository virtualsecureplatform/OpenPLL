"""Compare native PWL and TABLEFILE source values and knot breakpoints; fixture scope only."""
import csv,json,os,time,argparse,math
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute


def interpolate(points,t):
    if t<=points[0][0]:return points[0][1]
    for (a,x),(b,y) in zip(points,points[1:]):
        if t<=b:return x+(y-x)*((t-a)/(b-a))
    return points[-1][1]


def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    binaries=[ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce',ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce']
    cases={'constant':[(0.,.7),(4e-9,.7)],'irregular_ramps':[(0.,0.),(.13e-9,1.8),(.77e-9,-.2),(2.31e-9,.9),(4e-9,.1)],'plateau':[(0.,1.8),(.21e-9,1.8),(.37e-9,0.),(1.11e-9,0.),(1.8e-9,1.8),(4e-9,1.8)]}
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),*binaries]};artifacts={};results=[]
    save(output/'inputs.json',dict(input_sha256=pins,maximum_native_cases=12,native_memory_GiB=2,campaign_cap_s=600,automatic_identical_retry=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    try:
        with lease(1,2,deadline):
            for bi,binary in enumerate(binaries):
                for name,points in cases.items():
                    pair=[]
                    for kind in ['PWL','TABLEFILE']:
                        folder=output/(str(bi)+'_'+name+'_'+kind);folder.mkdir();data=folder/'samples.dat';data.write_text(''.join(format(t,'.17g')+' '+format(v,'.17g')+'\n' for t,v in points));deck=folder/'test.spice';csvfile=folder/'result.csv'
                        source='Vin input 0 PWL('+ ' '.join(format(t,'.17g')+' '+format(v,'.17g') for t,v in points)+')' if kind=='PWL' else 'Bin input 0 V={TABLEFILE("'+str(data)+'")}'
                        deck.write_text('* Boundary source representation fixture\n'+source+'\nRload input 0 1000\n.options nonlin reltol=1e-10 abstol=1e-13\n.tran 10p 6n 0 1n\n.print TRAN FORMAT=CSV PRECISION=17 FILE='+str(csvfile)+' V(input)\n.end\n')
                        pins.update({str(p):sha(p) for p in [data,deck]});verify(pins);save(output/'status.json',dict(state='native_source_representation_control',backend=bi,case=name,encoding=kind,release_ready=False))
                        execute([binary,'-a','-linsolv','umfpack_reuse',deck],folder/'native.log',deadline,2)
                        with csvfile.open() as f:
                            reader=csv.DictReader(f);rows=[]
                            for row in reader:
                                if not row.get('TIME') or row['TIME'].startswith('End'):continue
                                rows.append((float(row['TIME']),float(row['V(INPUT)'])))
                        if not rows or any(not math.isfinite(x) for r in rows for x in r) or rows[-1][0]!=6e-9:raise ValueError('complete finite native output required')
                        error=max(abs(v-interpolate(points,t)) for t,v in rows)
                        if error>1e-12:raise ValueError('native source differs from literal piecewise-linear data')
                        missing=[t for t,_ in points[1:] if not any(abs(t-x)<1e-21 for x,_ in rows)]
                        if missing:raise ValueError('native sample-knot breakpoint missing: '+str(missing))
                        pair.append(dict(encoding=kind,samples=len(rows),maximum_source_error_V=error,all_sample_knots_present=True,final_value_held=True))
                        artifacts.update({str(p):sha(p) for p in [csvfile,folder/'native.log']})
                    results.append(dict(binary=str(binary),case=name,encodings=pair))
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_twelve_native_controls_complete=True,literal_source_samples_and_knot_breakpoints_verified=True,fixture_absolute_voltage_tolerance=1e-12,fixture_knot_time_tolerance_s=1e-21,PLL_replay_accuracy_qualified=False,PLL_memory_reduction_demonstrated=False,release_ready=False));save(output/'status.json',dict(state='native_source_controls_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
