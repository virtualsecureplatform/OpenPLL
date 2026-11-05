#!/usr/bin/env python3
"""One bounded changed-solver DCO diagnostic, gated on controls and native GIDs."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
from run_DCO_domain_point_v3 import live_engines,model_files
from run_DCO_stock_threaded_point_v2 import rows
from retain_DCO_threaded_first_step_comparison import read_prefix

child=None

def stop(native):
    if native is not None and native.poll() is None:
        os.killpg(native.pid,signal.SIGTERM)
        try:native.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(native.pid,signal.SIGKILL);native.wait()

def main(args):
    global child
    root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
    out=args.output.resolve();out.mkdir(exist_ok=False);args.output=out
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    def status(state,**extra):
        save(out/'status.json',dict(state=state,runner_pid=os.getpid(),deadline_uptime=deadline,
            release_qualified=False,adopted=False,**extra))
    mapping=base/'DCO_wire_preconditioner_variable_map_001'
    proof=mapping/'assessment.json';identity=process(args.mapping_pid)
    assert identity['live'] and Path(identity['argv'][1]).name=='check_DCO_wire_preconditioner_variable_map.py'
    assert json.loads((mapping/'owner.json').read_text())['runner_pid']==args.mapping_pid
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        deadline_uptime=deadline,total_wall_limit_s=43200,dependency_wait_included_in_budget=True,
        mapping_runner_identity=identity,new_check_method='isolated_wire_C_preconditioned_GMRES',
        original_closed_campaign_extended=False,identical_native_retry=False))
    status('waiting_for_identified_variable_map_gate')
    while not proof.exists() and time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        current=process(args.mapping_pid)
        if not current['live'] or current['argv']!=identity['argv']:break
        time.sleep(1)
    if not proof.exists():
        save(out/'assessment.json',dict(native_started=False,reason='dependency_unavailable_or_check_deadline',
            dependency_identity=process(args.mapping_pid),release_qualified=False,adopted=False))
        status('dependency_unavailable_no_native_started');return
    gate=json.loads(proof.read_text())
    if not gate['full_DCO_variable_map_verified']:
        save(out/'assessment.json',dict(native_started=False,reason='native_variable_map_gate_nonpass',
            gate_assessment_sha256=digest(proof),release_qualified=False,adopted=False))
        status('dependency_nonpass_no_native_started');return
    controls=base/'wire_preconditioned_native_controls_002/assessment.json'
    assert json.loads(controls.read_text())['native_adapter_controls_passed']
    build=base/'wire_preconditioned_Xyce_002/assessment.json';built=json.loads(build.read_text())
    assert built['experimental_build_completed'];binary=Path(built['binary']);assert digest(binary)==built['binary_sha256']
    meta=base/'native_wire_preconditioner_metadata_001/assessment.json';model=json.loads(meta.read_text())
    metadata=Path(model['metadata_file']);assert digest(metadata)==model['metadata_sha256']
    original=base/'DCO_domain_nom_tt27_c0_f247_80ns_stock_serial_corrected_002'
    source=original/'point.cir';deck=out/'point.cir';deck.write_bytes(source.read_bytes())
    assert digest(deck)==digest(source)==digest(mapping/'point.cir')
    text=deck.read_text();assert '.tran 20p 80n 0 10p UIC' in text
    assert '.options TIMEINT RELTOL=1e-05 ABSTOL=1e-09' in text
    reference_text,reference=read_prefix(original/'point.cir.prn')
    retained=out/'retained_stock_first_step.prn';retained.write_text(reference_text)
    active=root/'verification/active_release.json';release=json.loads(active.read_text())
    assert release['target_mhz']==400 and release['supply_v']==1.8
    inputs=[Path(__file__),proof,controls,build,binary,meta,metadata,source,deck,retained,active,
        original/'point.cir.prn',root/'build/apptainer/openpll-release-modern.sif']
    for key in ['requirements','plan','presets']:
        p=root/release[key];assert digest(p)==release['sha256'][key];inputs.append(p)
    inputs+=model_files(deck,deadline)
    pins={str(p.resolve()):digest(p) for p in inputs}
    save(out/'input_manifest.json',dict(input_sha256=pins,
        physical_circuit_byte_identical_to_retained_serial_point=True,
        initial_bias_time_grid_and_tolerances_unchanged=True,
        experimental_solver_and_opt_in_environment_changed=True,
        full_DCO_variable_map_gate_passed=True,native_controls_gate_passed=True,
        parameters=dict(coarse=0,fine=247,corner='tt',temperature_C=27,supply_V=1.8,
            duration_ns=80,measure_start_ns=20,max_step_ps=10,reltol=1e-5,abstol=1e-9),
        native_address_space_limit_GiB=48,original_closed_campaign_extended=False))
    def limits():
        resource.setrlimit(resource.RLIMIT_AS,(48*1024**3,48*1024**3))
        resource.setrlimit(resource.RLIMIT_CPU,(43200,43201))
    while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if not live_engines():
                log=(out/'native.log').open('x')
                child=subprocess.Popen([str(binary),'-quiet','-o',str(deck),str(deck)],cwd=out,
                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits,
                    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OPENPLL_WIRE_PC=str(metadata)))
                log.close();break
        status('queued_for_exclusive_native_slot');time.sleep(1)
    if child is None:
        save(out/'assessment.json',dict(native_started=False,reason='check_deadline_before_admission',release_qualified=False))
        status('timeout_inconclusive_before_native');return
    wave=Path(str(deck)+'.prn');checked=False;timed_out=False;last_update=0.;failure=None
    status('native_experimental_point_running',native_pid=child.pid)
    try:
        while child.poll() is None:
            now=time.clock_gettime(time.CLOCK_BOOTTIME)
            if now>=deadline:timed_out=True;stop(child);break
            if now-last_update>=30:
                last_update=now;data=rows(wave)
                status('native_experimental_point_running',native_pid=child.pid,samples=len(data),
                    simulation_time_s=data[-1][0] if data else 0.,first_step_compared=checked)
                if not checked and len(data)>=2:
                    prefix,current=read_prefix(wave)
                    assert [r[0] for r in current]==[r[0] for r in reference]
                    dv=max(abs(a[1]-b[1]) for a,b in zip(current,reference))
                    di=max(abs(a[2]-b[2]) for a,b in zip(current,reference))
                    compared=out/'retained_experimental_first_step.prn';compared.write_text(prefix)
                    checked=dv<=1e-6 and di<=1e-10
                    save(out/'first_step_comparison.json',dict(first_step_equivalence_passed=checked,
                        maximum_voltage_difference_V=dv,maximum_supply_current_difference_A=di,
                        voltage_limit_V=1e-6,current_limit_A=1e-10,
                        source_prefix_sha256=digest(retained),experimental_prefix_sha256=digest(compared),
                        release_qualified=False))
                    if not checked:failure='first_step_equivalence_nonpass';stop(child);break
            time.sleep(1)
    finally:stop(child)
    code=child.returncode;data=rows(wave);metrics=None;completed=False
    if code==0 and wave.exists():
        content=wave.read_text();assert 'End of Xyce(TM) Simulation' in content
        assert data and all(math.isfinite(value) for row in data for value in row)
        assert all(a[0]<b[0] for a,b in zip(data,data[1:]))
        assert data[-1][0]>=80e-9*(1-1e-7)
        completed=True
        edges=[]
        for a,b in zip(data,data[1:]):
            if a[1]<.9<=b[1]:
                t=a[0]+(.9-a[1])*(b[0]-a[0])/(b[1]-a[1])
                if t>=20e-9:edges.append(t)
        if len(edges)>=4:
            metrics=dict(mhz=(len(edges)-1)/(edges[-1]-edges[0])*1e-6,periods=len(edges)-1,
                output_min_V=min(row[1] for row in data),output_max_V=max(row[1] for row in data))
    pc=[]
    for line in (out/'native.log').read_text().splitlines():
        match=re.fullmatch(r'OpenPLL_wire_PC call=(\d+) alpha=(\S+) iterations=(\d+) scaled_true_relative_residual=(\S+) seconds=(\S+) status=(\d+)',line)
        if match:pc.append(dict(call=int(match[1]),alpha=float(match[2]),iterations=int(match[3]),
            relative_residual=float(match[4]),elapsed_s=float(match[5]),status=int(match[6])))
    if completed:
        assert checked and pc
        assert all(math.isfinite(p['relative_residual']) and p['relative_residual']<=1e-12 for p in pc if p['status']==0)
    assert all(digest(Path(p))==sha for p,sha in pins.items())
    save(out/'assessment.json',dict(native_started=True,native_exit=code,timed_out=timed_out,failure=failure,
        completed_full_native_transient=completed,completed_diagnostic_oscillation=metrics is not None,
        metrics=metrics,samples=len(data),simulation_time_s=data[-1][0] if data else None,
        first_step_equivalence_passed=checked,adapter_linear_solves=len(pc),
        rejected_linear_solves=sum(p['status']!=0 for p in pc),
        input_sha256=pins,artifacts={str(p):digest(p) for p in [out/'native.log',wave] if p.exists()},
        source_model_and_frequency_convergence_qualified=False,full_parent_loading_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,
        original_closed_campaign_extended=False,identical_native_retry=False))
    status('completed_native_diagnostic' if completed and metrics is not None else
        ('timeout_inconclusive' if timed_out else (failure or 'native_or_oscillation_nonpass')),
        native_exit=code,metrics=metrics)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mapping-pid',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:main(args)
    except Exception as error:
        stop(child)
        if args.output.exists():
            save(args.output/'runner_failure.json',dict(error_type=type(error).__name__,message=str(error),
                native_stopped=True,release_qualified=False))
            save(args.output/'status.json',dict(state='runner_nonpass',runner_pid=os.getpid(),release_qualified=False))
        raise
