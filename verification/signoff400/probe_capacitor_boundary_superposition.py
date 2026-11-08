"""Native original/weighted-boundary RC controls against a closed-form state response."""
import argparse,csv,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute


def response(times,a,b,t,resistance,cunit):
    value=1.;tau=resistance*6*cunit
    for i in range(len(times)-1):
        if t<=times[i]:return value
        duration=min(t,times[i+1])-times[i]
        sa=(a[i+1]-a[i])/(times[i+1]-times[i]);sb=(b[i+1]-b[i])/(times[i+1]-times[i])
        equilibrium=1+resistance*cunit*(sa+3*sb)
        value=equilibrium+(value-equilibrium)*math.exp(-duration/tau)
        if t<=times[i+1]:return value
    return 1+(value-1)*math.exp(-(t-times[-1])/tau)


def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    binaries=[ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce',ROOT/'build/tools/xyce_umfpack_BSIM_junction_1292/Xyce'];pins={str(p):sha(p) for p in [Path(__file__).resolve(),*binaries]};artifacts={};results=[]
    times=[0.,.13e-9,.77e-9,2.31e-9,4e-9];cases={'constant':([.7]*5,[1.2]*5),'opposed_ramps':([0.,1.8,-.2,.9,.1],[.3,.1,1.4,-.1,.7]),'plateaus':([1.8,1.8,0.,0.,1.8],[0.,.5,.5,1.5,0.])}
    save(output/'inputs.json',dict(input_sha256=pins,maximum_native_cases=24,memory_GiB=2,CPU=29,resource_queue_cap_s=7200,native_campaign_cap_s=600,automatic_identical_retry=False,release_ready=False));save(output/'status.json',dict(state='waiting_for_global_CPU_RAM_budget',release_ready=False))
    try:
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
            for backend,binary in enumerate(binaries):
                for scale,resistance,cunit in [('pF_kohm',1e3,1e-12),('fF_Mohm',1e6,1e-15)]:
                    for name,(a,b) in cases.items():
                        observations=[]
                        for encoding in ['original','weighted']:
                            folder=output/(str(backend)+'_'+scale+'_'+name+'_'+encoding);folder.mkdir();csvfile=folder/'result.csv';deck=folder/'test.spice'
                            def source(node,values):return 'V'+node+' '+node+' 0 PWL('+ ' '.join(format(t,'.17g')+' '+format(v,'.17g') for t,v in zip(times,values))+')\n'
                            text='* Linear capacitor-boundary equivalence control\nVbias supply 0 1\nRload supply out '+format(resistance,'.17g')+'\nCg out 0 '+format(2*cunit,'.17g')+'\n'
                            if encoding=='original':text+=source('a',a)+source('b',b)+'Ca out a '+format(cunit,'.17g')+'\nCb out b '+format(3*cunit,'.17g')+'\n'
                            else:text+=source('aggregate',[(x+3*y)/4 for x,y in zip(a,b)])+'Caggregate out aggregate '+format(4*cunit,'.17g')+'\n'
                            text+='.options nonlin reltol=1e-10 abstol=1e-15\n.options timeint reltol=1e-9 abstol=1e-12\n.tran 1p 6n 0 50p\n.print TRAN FORMAT=CSV PRECISION=17 FILE='+str(csvfile)+' V(out)\n.end\n';deck.write_text(text);pins[str(deck)]=sha(deck);verify(pins)
                            save(output/'status.json',dict(state='native_capacitor_superposition_control',backend=backend,scale=scale,case=name,encoding=encoding,release_ready=False));execute([binary,'-a','-linsolv','umfpack_reuse',deck],folder/'native.log',deadline,2)
                            rows=[]
                            with csvfile.open() as stream:
                                for row in csv.DictReader(stream):
                                    if row.get('TIME') and not row['TIME'].startswith('End'):rows.append((float(row['TIME']),float(row['V(OUT)'])))
                            if not rows or rows[0][0]!=0 or not math.isclose(rows[-1][0],6e-9,rel_tol=0,abs_tol=1e-21) or any(not math.isfinite(x) for row in rows for x in row):raise ValueError('complete finite native RC capture required')
                            error=max(abs(v-response(times,a,b,t,resistance,cunit)) for t,v in rows)
                            if error>1e-7:raise ValueError('native RC response differs from closed-form state solution: '+str(error))
                            if any(not any(abs(t-x)<1e-21 for x,_ in rows) for t in times[1:]):raise ValueError('source-knot breakpoint missing')
                            observations.append(dict(encoding=encoding,samples=len(rows),maximum_closed_form_voltage_error=error,all_source_knots_present=True));artifacts.update({str(p):sha(p) for p in [csvfile,folder/'native.log']})
                        results.append(dict(backend=str(binary),scale=scale,case=name,observations=observations));save(output/'progress.json',results)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_twenty_four_native_RC_controls_complete=True,original_and_aggregated_response_matches_closed_form=True,fixture_absolute_voltage_error_limit=1e-7,fixture_time_knot_tolerance_s=1e-21,actual_PLL_native_equivalence_verified=False,aggregation_roundoff_for_PLL_qualified=False,release_ready=False));save(output/'status.json',dict(state='native_capacitor_superposition_controls_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
