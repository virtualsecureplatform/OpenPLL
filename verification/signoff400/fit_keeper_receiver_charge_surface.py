"""Fit a positive-capacitance charge surface; do not substitute recorded internal voltage."""
import json
import os
from pathlib import Path
import time
import numpy as np
from common_v3 import ROOT, save, sha, verify
from resources import lease
from audit_keeper_DCO_driver_C_cut import capacitance

KNOTS=np.linspace(0.,1.8,11)


def features(v,mid):
    if not np.isfinite(v).all() or not np.isfinite(mid).all() or v.shape!=mid.shape:
        raise ValueError('aligned finite voltage observations required')
    columns=[np.clip(v-low,0.,high-low) for low,high in zip(KNOTS[:-1],KNOTS[1:])]
    columns.append(v-mid+1.8)
    return np.column_stack(columns)


def positive_fit(x,y):
    if x.ndim!=2 or y.shape!=(len(x),) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('finite aligned charge data required')
    g=x.T@x
    b=x.T@y
    if np.any(np.diag(g)<=0):
        raise ValueError('every charge basis must be exercised')
    c=np.zeros(x.shape[1])
    for iteration in range(20000):
        largest=0.
        for k in range(len(c)):
            new=max(0.,c[k]+(b[k]-g[k]@c)/g[k,k])
            largest=max(largest,abs(new-c[k]))
            c[k]=new
        if largest<1e-10:
            return c,iteration+1
    raise RuntimeError('positive charge fit did not converge')


def intrinsic_charge(t,v,current,out,mid,capacitors):
    q=-np.r_[0.,np.cumsum((current[:-1]+current[1:])*.5*np.diff(t))]
    voltage={'A':v,'X':out,'a_114_74#':mid,'VPWR':np.full(len(t),1.8),
             'VPB':np.full(len(t),1.8),'VGND':np.zeros(len(t)),'VNB':np.zeros(len(t))}
    explicit=np.zeros(len(t))
    for cap in capacitors:
        a,b=cap['nodes']
        other=b if a=='A' else a
        if other not in voltage:
            raise ValueError('all explicit capacitor terminal voltages required')
        explicit+=float(capacitance(cap['literal']))*(v-voltage[other])
    return (q-(explicit-explicit[0]))*1e15


def run():
    base=ROOT/'build/signoff400'
    source=base/'selected_keeper_clock_buffer_charge_deembedded_1527'
    output=base/'selected_keeper_receiver_charge_surface_1529'
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{19})
    receipt=source/'assessment.json'
    a=json.loads(receipt.read_text())
    verify(a['input_sha256'])
    verify(a['artifacts'])
    if a['explicit_input_C_deembedding_complete'] is not True:
        raise ValueError('complete deembedded native measurements required')
    plan=json.loads((source/'plan.json').read_text())
    caps=json.loads((source/'explicit_input_capacitors.json').read_text())
    files=[receipt,source/'plan.json',source/'explicit_input_capacitors.json',Path(__file__).resolve(),
           Path(__file__).with_name('audit_keeper_DCO_driver_C_cut.py')]
    pins={str(p):sha(p) for p in files}
    save(output/'plan.json',dict(training_corners=plan['corners'],training_cases=plan['cases'],
         input_voltage_knots_V=KNOTS.tolist(),model='positive piecewise input C plus positive Miller C',
         prospective_validation=dict(input_full_ramp_ps=100,output_load_fF=200,frequency_MHz=400),
         prospective_validation_not_yet_measured=True,release_ready=False))
    pins[str(output/'plan.json')]=sha(output/'plan.json')
    models={}
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
        for corner in plan['corners']:
            wave=source/corner/'waveform.dat'
            if a['artifacts'].get(str(wave))!=sha(wave):
                raise ValueError('completed waveform identity required')
            x=np.loadtxt(wave,skiprows=1)
            t=x[:,0]
            sample=np.r_[np.linspace(8e-9,14e-9,2049),np.linspace(20e-9,26e-9,2049)]
            matrices=[]
            charges=[]
            for i,case in enumerate(plan['cases']):
                v,cur,out,mid=[x[:,1+4*i+j] for j in range(4)]
                q=intrinsic_charge(t,v,cur,out,mid,caps)
                matrices.append(features(np.interp(sample,t,v),np.interp(sample,t,mid)))
                charges.append(np.interp(sample,t,q))
            design,target=np.vstack(matrices),np.concatenate(charges)
            coefficients,iterations=positive_fit(design,target)
            residual=design@coefficients-target
            scale=float(np.max(target)-np.min(target))
            if scale<=0:
                raise ValueError('nonzero measured gate charge swing required')
            models[corner]=dict(input_capacitances_fF=coefficients[:-1].tolist(),
                Miller_capacitance_fF=float(coefficients[-1]),iterations=iterations,
                maximum_training_charge_error_fC=float(np.max(np.abs(residual))),
                RMS_training_charge_error_fC=float(np.sqrt(np.mean(residual**2))),
                maximum_training_error_relative_to_charge_swing=float(np.max(np.abs(residual))/scale),
                conditional_on_observed_internal_voltage=True)
            pins[str(wave)]=sha(wave)
    model=output/'charge_surfaces.json'
    save(model,dict(input_voltage_knots_V=KNOTS.tolist(),corners=models,
         units=dict(capacitance='fF',charge='fC',voltage='V')))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(model):sha(model)},
         trained_corners=5,training_only=True,all_capacitance_coefficients_nonnegative=True,
         maximum_training_error_relative_to_charge_swing=max(v['maximum_training_error_relative_to_charge_swing'] for v in models.values()),
         causal_internal_voltage_model_available=False,independent_periodic_validation_complete=False,
         full_flat_C_stitching_qualified=False,clock_receiver_model_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='conditional_receiver_charge_surfaces_fitted',release_ready=False))


if __name__=='__main__':
    run()
