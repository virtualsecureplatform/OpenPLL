"""Verify actual Xyce UIC capacitor-voltage initialization on an RC control.

This checks supported simulator semantics, not nonlinear PLL state restart.
"""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from assess_selected_detector_prefix import read_prefix


def run(output,image):
    os.sched_setaffinity(0,{28});output.mkdir(parents=True,exist_ok=False)
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
    pins={str(p):sha(p)for p in (binary,image,Path(__file__).resolve(),Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('resources.py'),Path(__file__).with_name('common_v3.py'))}
    artifacts={};results=[];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+120
    for label,initial in (('zero',0),('charged',1.2)):
        folder=output/label;folder.mkdir();deck=folder/'profile.spice';raw=folder/'profile.raw'
        deck.write_text(f'Native UIC capacitor initialization control\nR1 node 0 1k\nC1 node 0 1p\n.IC V(node)={initial}\n.options timeint reltol=1e-7 abstol=1e-12\n.options nonlin reltol=1e-8 abstol=1e-12\n.tran 1p 5n 0 5p UIC\n.print tran format=raw precision=17 file={raw} V(node)\n.end\n')
        pins[str(deck)]=sha(deck)
        with lease(1,1,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],folder/'native.log',deadline,1)
        rows,info=read_prefix(raw,dict(capacitor_voltage='node'))
        if info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-5e-9)>1e-18 or rows[0][0]!=0:raise ValueError('complete native UIC control required')
        error=max(abs(row[1]-initial*math.exp(-row[0]/1e-9))for row in rows)
        if abs(rows[0][1]-initial)>1e-12 or error>1e-5:raise ValueError('UIC voltage or RC trajectory differs from analytic control')
        discharged=sum((b[0]-a[0])*(a[1]+b[1])/2000 for a,b in zip(rows,rows[1:]))
        charge_change=1e-12*(rows[0][1]-rows[-1][1])
        if abs(discharged-charge_change)>1e-17:raise ValueError('UIC capacitor charge balance differs')
        results.append(dict(case=label,initial_voltage_v=initial,maximum_analytic_voltage_error_v=error,discharged_charge_c=discharged,stored_charge_change_c=charge_change,samples=len(rows)))
        artifacts.update({str(p):sha(p)for p in (raw,folder/'native.log')})
    verify(pins);verify(artifacts)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
        actual_native_UIC_voltage_initialization_verified=True,analytic_RC_decay_and_charge_balance_verified=True,
        nonlinear_PLL_restart_qualified=False,release_ready=False));print(json.dumps(results))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('output','image'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.output.resolve(),a.image.resolve())
