"""Resolve the remaining body-response gap around drain/source reversal; diagnostic only."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from common import ROOT, save, sha, verify
from compiled_charge import execute
from resources import identity, lease
from run_MOS_backend_case_v2 import deck_body
from probe_native_junction_alias_v2 import table
from check_current_generic_poly_models_v3 import numeric


def work(output, deadline):
    base=ROOT/'build/signoff400';source=base/'startup_timing_MOS_body_response_001'
    retained=base/'startup_timing_CV_derivative_reference_comparison_001/assessment.json'
    build=base/'startup_timing_CV_derivative_reference_build_001/assessment.json'
    a,b=[json.loads(p.read_text()) for p in (retained,build)]
    verify(a['input_sha256'])
    ng=Path(b['diagnostic_binary']);xyce=Path('/opt/xyce/bin/Xyce')
    if sha(ng)!=b['artifacts'][str(ng)]:raise ValueError('corrected diagnostic reference changed')
    fixtures_path=source/'ac/fixtures.json';original_deck=source/'ac/ngspice.cir'
    parent=json.loads((source/'assessment.json').read_text())
    for p in (fixtures_path,original_deck):
        if sha(p)!=parent['artifacts'][str(p)]:raise ValueError('retained physical fixtures changed')
    fixtures=json.loads(fixtures_path.read_text())
    profiles=[next(f['profile'] for f in fixtures if f['profile']['profile_id']==pid) for pid in (1002,2002)]
    headers=[line for line in original_deck.read_text().splitlines() if re.match(r'^\s*\.(lib|include)\s',line,re.I)]
    if not headers:raise ValueError('retained model headers required')
    grid=dict(drain_source_bias_magnitudes_v=[-1e-3,-1e-6,-1e-9,-1e-12,0,1e-12,1e-9,1e-6,1e-3],
              reverse_body_bias_magnitudes_v=[0],AC_gate_source_bias_magnitudes_v=[.9],AC_terminal_excitations=['bulk'])
    rows,body,quantities,reference=deck_body(profiles,grid,'ac')
    save(output/'fixtures.json',rows)
    paths=[retained,build,fixtures_path,original_deck,source/'assessment.json',ng,xyce,Path(__file__).resolve(),
           Path(__file__).with_name('run_MOS_backend_case_v2.py'),Path(__file__).with_name('probe_native_junction_alias_v2.py'),
           Path(__file__).with_name('check_current_generic_poly_models_v3.py')]
    pins=dict(a['input_sha256']);pins.update({str(p):sha(p) for p in paths})
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    common=[*headers,*body]
    data=output/'ngspice.dat';ngdeck=output/'ngspice.cir';xydeck=output/'xyce.cir'
    ngdeck.write_text('\n'.join(['* Diagnostic only: zero-VDS neighborhood, unchanged retained model views.',*common,
        '.temp -40','.options reltol=1e-10 abstol=1e-20 gmin=1e-18','.control','set wr_singlescale',
        'set wr_vecnames','set numdgt=17','ac lin 3 1e3 799999000','wrdata '+str(data)+' '+' '.join(reference),
        'quit','.endc','.end'])+'\n')
    xydeck.write_text('\n'.join(['* Diagnostic only: zero-VDS neighborhood, unchanged retained model views.',*common,
        '.options device temp=-40 gmin=1e-18','.options nonlin reltol=1e-10 abstol=1e-20',
        '.ac lin 2 1e3 4e8','.print ac precision=16 '+' '.join(quantities),'.end'])+'\n')
    pins.update({str(p):sha(p) for p in (ngdeck,xydeck,output/'fixtures.json')})
    save(output/'input_manifest.json',dict(input_sha256=pins,diagnostic=True,release_qualified=False))
    save(output/'status.json',dict(state='running_corrected_reference_zero_VDS_neighborhood',release_qualified=False))
    execute([ng,'-b',ngdeck],output/'ngspice.log',deadline,4)
    ref=numeric(data,len(reference)+1,0)
    ref=[r for r in ref if r[0] in (1e3,4e8)]
    if len(ref)!=2:raise ValueError('unique two reference frequencies required')
    save(output/'status.json',dict(state='running_native_zero_VDS_neighborhood',release_qualified=False))
    execute([xyce,'-linsolv','KLU','-quiet','-o',xydeck,xydeck],output/'xyce.log',deadline,4)
    native_path=Path(str(xydeck)+'.FD.prn');native=table(native_path,len(quantities),2)
    results=[]
    lookup={(r['profile']['profile_id'],r['drain']):i for i,r in enumerate(rows)}
    for x,y in zip(ref,native,strict=True):
        if x[0]!=y[1]:raise ValueError('aligned frequencies required')
        for drain in grid['drain_source_bias_magnitudes_v']:
            result=dict(frequency_hz=x[0],signed_drain_bias_v=drain,terminals={})
            for electrode,name in enumerate(('drain','gate','source','bulk')):
                values={}
                for pid,label in ((1002,'body1'),(2002,'body0')):
                    k=lookup[pid,drain]*8+electrode*2
                    values['reference_'+label]=complex(x[1+k],x[2+k]);values['native_'+label]=complex(y[2+k],y[3+k])
                delta=values['native_body1']-values['reference_body1']
                result['terminals'][name]=dict(phasors_A={k:[v.real,v.imag] for k,v in values.items()},
                    native_minus_reference_body1_A=[delta.real,delta.imag],
                    imaginary_gap_over_omega_F=delta.imag/(2*math.pi*x[0]),
                    reference_body1_minus_body0_A=[(values['reference_body1']-values['reference_body0']).real,
                                                  (values['reference_body1']-values['reference_body0']).imag],
                    native_body1_minus_body0_A=[(values['native_body1']-values['native_body0']).real,
                                               (values['native_body1']-values['native_body0']).imag])
            results.append(result)
    verify(pins)
    artifacts={str(p):sha(p) for p in (data,ngdeck,xydeck,native_path,output/'ngspice.log',output/'xyce.log',output/'fixtures.json')}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
         scope='TT -40C high-Vt PFET, bulk excitation at |VGS|=.9V, signed VDS neighborhood, body1/body0',
         diagnostic=True,foundry_models_modified=False,release_model_changed=False,
         MOS_backend_compatibility_qualified=False,release_qualified=False))
    save(output/'status.json',dict(state='zero_VDS_body_response_diagnosis_complete',release_qualified=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--inside',action='store_true')
    parser.add_argument('--deadline',type=float);args=parser.parse_args();output=args.output.resolve()
    if args.inside:return work(output,args.deadline)
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    try:
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',
            ROOT/'build/apptainer/openpll-release-modern.sif',
            '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',
            Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',output],
            output/'controller.log',deadline,4)
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_qualified=False));raise


if __name__=='__main__':main()
