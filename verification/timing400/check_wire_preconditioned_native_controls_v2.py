#!/usr/bin/env python3
"""Gate the experimental adapter on stock-correlated nonlinear native controls."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import numpy as np
from scipy.sparse import coo_matrix
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines,model_files
from check_stock_threaded_solver_controls_v2 import read_wave,crossing


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--build-runner-pid',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]; base=root/'build/timing400/release_001'
    args.output=args.output.resolve(); args.output.mkdir(exist_ok=False)
    build=base/'wire_preconditioned_Xyce_002'; proof=build/'assessment.json'
    identity=process(args.build_runner_pid)
    assert identity['live'] and Path(identity['argv'][1]).name=='build_wire_preconditioned_Xyce_v2.py'
    assert json.loads((build/'owner.json').read_text())['runner_pid']==args.build_runner_pid
    save(args.output/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        build_runner_identity=identity,maximum_build_wait_s=1900,control_stage_wall_limit_s=600,
        completed_qualification_campaign_extended=False,full_DCO_restarted=False))
    def status(state,**extra):
        save(args.output/'status.json',dict(state=state,runner_pid=os.getpid(),release_qualified=False,adopted=False,**extra))
    status('waiting_for_identified_experimental_build')
    wait_end=time.monotonic()+1900
    while not proof.exists() and time.monotonic()<wait_end:
        current=process(args.build_runner_pid)
        if not current['live'] or current['argv']!=identity['argv']: break
        time.sleep(1)
    if not proof.exists(): status('build_unavailable_no_native_control_started'); return
    built=json.loads(proof.read_text())
    if not built['experimental_build_completed']: status('build_nonpass_no_native_control_started'); return
    binary=Path(built['binary']); assert digest(binary)==built['binary_sha256']
    stock=base/'stock_serial_Xyce_001/xyce-install/bin/Xyce'
    golden=Path('/opt/xyce/bin/Xyce')
    deadline=time.monotonic()+600
    save(args.output/'control_stage_start.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=600))
    source=base/'stock_threaded_mesh_controls_001/KLU_1/control.cir'
    original=source.read_text(); assert original.count('.end')==1
    additions='Cwithin a input 20f\nCdevice output input 5f\nCcouple_mesh mesh17 mesh45 30f\nCgap mesh0 mesh1 7f\n'
    circuit=original.replace('.end',additions+'.end')
    deck=args.output/'names_control.cir'; deck.write_text(circuit)
    pins={str(p.resolve()):digest(p) for p in [Path(__file__),proof,binary,stock,golden,source,
        root/'build/apptainer/openpll-release-modern.sif',deck,
        Path(__file__).with_name('check_stock_threaded_solver_controls_v2.py')]}
    for path in model_files(deck,time.clock_gettime(time.CLOCK_BOOTTIME)+600): pins[str(path)]=digest(path)
    receipts=[]
    def run(label,engine,point,extra=(),metadata=None):
        assert time.monotonic()<deadline
        folder=args.output/label; folder.mkdir(exist_ok=False)
        command=[str(engine),'-quiet',*extra]
        if not extra: command+=['-o',str(point)]
        command+=[str(point)]
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        env.pop('OPENPLL_WIRE_PC',None)
        if metadata is not None: env['OPENPLL_WIRE_PC']=str(metadata)
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            assert not live_engines(),'Do not overlap this control with a full native engine'
            before=time.monotonic()
            with (folder/'native.log').open('x') as log:
                child=subprocess.Popen(command,cwd=folder,stdout=log,stderr=subprocess.STDOUT,
                    env=env,start_new_session=True)
                status('native_control_running',case=label,native_pid=child.pid)
                timed_out=False
                try: code=child.wait(timeout=min(120,deadline-time.monotonic()))
                except subprocess.TimeoutExpired:
                    timed_out=True; os.killpg(child.pid,signal.SIGTERM)
                    try: child.wait(timeout=5)
                    except subprocess.TimeoutExpired: os.killpg(child.pid,signal.SIGKILL); child.wait()
                    code=child.returncode
        receipts.append(dict(case=label,native_exit=code,timed_out=timed_out,elapsed_s=time.monotonic()-before))
        save(args.output/'native_receipts.json',receipts)
        assert code==0,receipts[-1]
        return folder
    def names(path):
        lines=path.read_text().splitlines(); assert lines[0]=='HEADER'
        result={int(line.split()[0]):line.split()[1].upper() for line in lines[1:]}
        assert set(result)==set(range(len(result))) and len(set(result.values()))==len(result)
        return [result[i] for i in range(len(result))]
    stock_names=args.output/'stock.names'; candidate_names=args.output/'candidate.names'
    run('stock_names',stock,deck,['-namesfile',str(stock_names)])
    run('candidate_names',binary,deck,['-namesfile',str(candidate_names)])
    variables=names(candidate_names); assert variables==names(stock_names)
    lookup={name:i for i,name in enumerate(variables)}; n=len(variables)
    couplings=[('A','B',1e-12,0),('A','INPUT',-20e-15,1),('OUTPUT','INPUT',-5e-15,1),
        ('MESH17','MESH45',-30e-15,0),('MESH0','MESH1',-7e-15,1)]
    rows=[]; columns=[]; values=[]; preserved={}
    for first,second,value,keep in couplings:
        i,j=lookup[first],lookup[second]
        rows.extend((i,j)); columns.extend((j,i)); values.extend((value,value))
        preserved[i*n+j]=preserved[j*n+i]=keep
    C=coo_matrix((values,(rows,columns)),shape=(n,n)).tocsr(); C.sort_indices()
    rr=np.repeat(np.arange(n),np.diff(C.indptr))
    keep=np.array([preserved[int(i)*n+int(j)] for i,j in zip(rr,C.indices)],dtype=np.uint8)
    sample=1-keep
    metadata=args.output/'wire_C.bin'
    with metadata.open('xb') as handle:
        handle.write(b'OPLLCAP1'); np.array([n,C.nnz],dtype='<i4').tofile(handle)
        np.asarray(C.indptr,dtype='<i4').tofile(handle); np.asarray(C.indices,dtype='<i4').tofile(handle)
        np.asarray(C.data,dtype='<f8').tofile(handle); keep.tofile(handle); sample.tofile(handle)
    assert n==77 and C.nnz==10 and sum(keep)==6 and sum(sample)==4
    pins.update({str(p):digest(p) for p in [stock_names,candidate_names,metadata]})
    comparisons=[]
    def compare(label,reference,data):
        grid=np.linspace(0,8e-9,8001)
        differences=[float(max(abs(np.interp(grid,reference[:,0],reference[:,i])-
            np.interp(grid,data[:,0],data[:,i])))) for i in range(1,5)]
        scale=max(float(max(abs(reference[:,4]))),float(max(abs(data[:,4]))),1e-12)
        a,b=crossing(reference),crossing(data); assert len(a)==len(b)
        edge=max(abs(x-y) for x,y in zip(a,b))
        assert max(differences[:2])<1e-5 and differences[2]<2e-3
        assert differences[3]<1e-3*scale+1e-10 and edge<1e-13
        comparisons.append(dict(case=label,voltage_differences_V=differences[:3],
            supply_current_difference_A=differences[3],rising_crossing_difference_s=edge))
    adapter_checks=[]
    for variant in ['baseline','timestep_holdout','tolerance_holdout']:
        text=circuit
        if variant=='timestep_holdout':
            assert text.count('.tran 2p 8n 0 1p')==1
            text=text.replace('.tran 2p 8n 0 1p','.tran 2p 8n 0 .47p')
        if variant=='tolerance_holdout':
            assert text.count('RELTOL=1e-7 ABSTOL=1e-12')==1
            text=text.replace('RELTOL=1e-7 ABSTOL=1e-12','RELTOL=1e-8 ABSTOL=1e-13')
        reference=None
        configurations=[('stock',golden,None),('adapter',binary,metadata)]
        if variant=='baseline': configurations.append(('disabled',binary,None))
        for method,engine,meta in configurations:
            label=variant+'_'+method; point=args.output/(label+'.cir'); point.write_text(text)
            pins[str(point)]=digest(point)
            folder=run(label,engine,point,metadata=meta)
            wave=read_wave(Path(str(point)+'.prn'))
            if method=='stock': reference=wave; continue
            compare(label,reference,wave)
            logs=(folder/'native.log').read_text().splitlines()
            matches=[re.fullmatch(r'OpenPLL_wire_PC call=(\d+) alpha=(\S+) iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(\d+)',line)
                for line in logs if line.startswith('OpenPLL_wire_PC call=')]
            if method=='disabled': assert not matches; continue
            assert matches and all(matches)
            calls=[int(m[1]) for m in matches]; assert calls==list(range(1,len(calls)+1))
            alpha=np.array([float(m[2]) for m in matches]); residual=np.array([float(m[4]) for m in matches])
            assert np.isfinite(alpha).all() and np.isfinite(residual).all()
            assert np.min(alpha)==0 and np.max(alpha)>0 and len(set(alpha))>=4
            assert np.max(residual)<=1e-12 and all(int(m[6])==0 for m in matches)
            adapter_checks.append(dict(case=label,linear_solves=len(calls),maximum_true_scaled_relative_residual=float(max(residual)),
                distinct_capacitance_multipliers=len(set(alpha)),maximum_iterations=max(int(m[3]) for m in matches)))
    assert all(digest(Path(p))==sha for p,sha in pins.items())
    artifacts={str(p):digest(p) for p in args.output.rglob('*') if p.is_file() and p.suffix in ['.log','.prn','.names','.bin']}
    save(args.output/'assessment.json',dict(native_adapter_controls_passed=True,case_receipts=receipts,
        comparisons=comparisons,adapter_checks=adapter_checks,input_sha256=pins,artifacts=artifacts,
        native_control_variable_maps_identical=True,DC_and_successive_transient_Newton_steps_tested=True,
        timestep_and_tolerance_holdouts_tested=True,full_DCO_variable_map_verified=False,
        full_DCO_transient_completed=False,general_simulator_equivalence_qualified=False,
        release_qualified=False,adopted=False))
    status('completed_native_adapter_controls')


if __name__=='__main__': main()
