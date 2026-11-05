#!/usr/bin/env python3
"""Serial native waveform controls for the opt-in KLS/GMRES backend."""
import fcntl,json,os,resource,signal,subprocess,time
from pathlib import Path
import numpy as np
from compile_local_C_operators_v2 import digest,save
from check_stock_threaded_solver_controls_v2 import read_wave,crossing
from run_DCO_domain_point_v3 import live_engines
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
campaign=base/'KLS_detailed_profile_001';deadline=json.loads((campaign/'owner.json').read_text())['deadline_uptime']
proof=campaign/'native_build_002/assessment.json';built=json.loads(proof.read_text());assert built['adapter_regression_passed']
binary=Path(built['binary']);assert digest(binary)==built['binary_sha256']
prior=base/'bounded_reuse_native_controls_002';reference=json.loads((prior/'assessment.json').read_text())
audit=base/'bounded_reuse_native_controls_audit_002/assessment.json'
assert json.loads(audit.read_text())['completed_native_control_audit_passed']
out=campaign/'native_controls_001';out.mkdir(exist_ok=False)
pins={str(p):digest(p) for p in (Path(__file__).resolve(),campaign/'owner.json',proof,binary,prior/'assessment.json',audit)}
selected=json.loads((campaign/'selected_candidate.json').read_text())
receipts=[];comparisons=[];child=None
lock=(base.parent/'guarded_native_admission.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not live_engines()
def stop():
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
def names(p):
    rows={int(t.split()[0]):t.split()[1].upper() for t in p.read_text().splitlines()[1:]}
    assert set(rows)==set(range(len(rows)))
    return [rows[i] for i in range(len(rows))]
def limits():resource.setrlimit(resource.RLIMIT_AS,(6*1024**3,6*1024**3))
try:
    for variant in ['default_trapezoid','gear_baseline','gear_timestep_holdout','gear_tolerance_holdout']:
        original=prior/(variant+'_stock.cir');wave=Path(str(original)+'.prn')
        assert digest(original)==reference['input_sha256'][str(original)]
        assert digest(wave)==reference['artifacts'][str(wave)]
        metadata=prior/('wire_C_default.bin' if variant=='default_trapezoid' else 'wire_C.bin')
        oldnames=prior/('default_candidate.names' if variant=='default_trapezoid' else 'candidate.names')
        for p in (original,wave,metadata,oldnames):pins[str(p)]=digest(p)
        folder=out/variant;folder.mkdir()
        old='.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0'
        text=original.read_text();assert text.count(old)==1
        deck=folder/'control.cir';deck.write_text(text.replace(old,'.options LINSOL TYPE=KLS KLS_THREADS=4 TR_PARTITION=0 TR_AMD=0'))
        pins[str(deck)]=digest(deck)
        env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_WAIT_POLICY='PASSIVE',OPENPLL_WIRE_PC=str(metadata))
        env.pop('OPENPLL_PACKED_CONSTANT_CAPS',None)
        env.update(OPENPLL_KLS_COMPARE_THREADS=str(selected['threads']),OPENPLL_KLS_COMPARE_POLICY='application_managed')
        for stage in ['names','wave']:
            command=[str(binary),'-quiet']
            command+=['-namesfile',str(folder/'candidate.names')] if stage=='names' else ['-o',str(folder/'control')]
            command+=[str(deck)]
            remaining=min(120,deadline-300-time.clock_gettime(time.CLOCK_BOOTTIME));assert remaining>0
            save(out/'status.json',dict(state='running_'+variant+'_'+stage,release_qualified=False))
            start=time.monotonic()
            with (folder/(stage+'.log')).open('x') as log:
                child=subprocess.Popen(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
                save(folder/(stage+'_launch.json'),dict(pid=child.pid,command=command,automatic_identical_retry=False))
                code=child.wait(timeout=remaining)
            receipts.append(dict(case=variant,stage=stage,exit_code=code,wall_s=time.monotonic()-start));save(out/'receipts.json',receipts)
            assert code==0
            if stage=='names':assert names(folder/'candidate.names')==names(oldnames)
        log=(folder/'wave.log').read_text();assert 'OpenPLL_KLS_PC nnz=' in log and 'OpenPLL_wire_PC call=' in log
        native=read_wave(folder/'control.prn');ref=read_wave(wave);grid=np.linspace(0,8e-9,8001)
        differences=[float(max(abs(np.interp(grid,ref[:,0],ref[:,i])-np.interp(grid,native[:,0],native[:,i])))) for i in range(1,5)]
        a,b=crossing(ref),crossing(native);assert len(a)==len(b);edge=max(abs(x-y) for x,y in zip(a,b))
        current_scale=max(float(max(abs(ref[:,4]))),float(max(abs(native[:,4]))),1e-12)
        assert max(differences[:2])<1e-5 and differences[2]<2e-3
        assert differences[3]<1e-3*current_scale+1e-10 and edge<1e-13
        comparisons.append(dict(case=variant,signal_maximum_absolute_differences=differences,maximum_rising_crossing_difference_s=edge))
    for p,sha in pins.items():assert digest(Path(p))==sha,p
    save(out/'assessment.json',dict(input_sha256=pins,receipts=receipts,comparisons=comparisons,native_waveform_controls_passed=True,
        signed_capacitance_retained=True,timestep_and_tolerance_holdouts_passed=True,original_full_equation_residual_limit=1e-12,
        KLS_certification_disabled=True,full_equation_residual_check_retained=True,selected_candidate=selected,release_qualified=False,full_DCO_speedup_demonstrated=False))
    save(out/'status.json',dict(state='completed_native_controls',release_qualified=False))
except Exception as e:
    stop();save(out/'failure_receipt.json',dict(error_type=type(e).__name__,message=str(e),release_qualified=False));raise
finally:stop()
