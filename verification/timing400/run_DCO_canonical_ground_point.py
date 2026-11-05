#!/usr/bin/env python3
"""Replace redundant external zero-volt constraints with exact SPICE ground.

Keep the entire physical candidate byte-identical, including every finite-R
vertex, capacitance, device, point connector and nonzero/dynamic source. Filter
only now-grounded public initial-condition entries. No model approximation.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from canonical_zero_voltage_nodes import canonicalize
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines
from run_DCO_seeded_C_free_DC import read_bias


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--prior',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--replace-native-pid',type=int,required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    controls=base/'zero_voltage_canonicalization_controls_001/assessment.json'
    assert json.loads(controls.read_text())['native_voltage_constraint_canonicalization_controls_passed']
    prior_manifest=args.prior/'input_manifest.json'
    prior=json.loads(prior_manifest.read_text());params=prior['parameters']
    original=args.prior/'point.cir';old=original.read_text()
    # This intentionally narrow transform accepts the frozen flat testbench,
    # never arbitrary hierarchical source scopes or wildcard observations.
    assert not any(s.lower().startswith('.subckt') for s in old.splitlines())
    assert [s for s in old.splitlines() if s.lower().startswith('.print ')]==[
        '.print TRAN FORMAT=STD PRECISION=16 V(PLLOUT) I(VVPWR)']
    transformed,aliases,removed=canonicalize(old)
    assert len(removed)==296 and aliases['VGND']=='0' and aliases['VNB']=='0'
    assert 'VPWR' not in aliases and 'VPB' not in aliases and 'RESET_N' not in aliases
    assert all(r['source'].upper()!='VVPWR' for r in removed)
    assert '.tran 20p 80n 0 10p UIC' in transformed
    assert '.options LINSOL TYPE=KLU TR_PARTITION=0 TR_AMD=0' in transformed
    assert len([s for s in transformed.splitlines() if s.startswith('V')])==11
    initial=Path(params['initial_bias']).resolve()
    initial_values=read_bias(initial)
    assert len(initial_values)==174508
    assert all(abs(initial_values[name])<1e-12 for name in aliases)
    args.output.mkdir(exist_ok=False)
    save(args.output/'owner.json',dict(original_owner=str(owner.resolve()),deadline_uptime=deadline,
        started_utc=datetime.now(timezone.utc).isoformat(),runner_pid=os.getpid(),budget_restarted=False))
    def status(state,**more):
        save(args.output/'status.json',dict(state=state,runner_pid=os.getpid(),deadline_uptime=deadline,**more))
    status('preparing_exact_ground_coordinate_change')
    filtered=args.output/'initial_bias_canonical_ground.ic'
    rows=[]
    for line in initial.read_text().splitlines():
        match=re.fullmatch(r'\s*\.IC\s+V\(([^)]+)\)\s*=\s*([-+.eE0-9]+)\s*',line,re.I)
        assert match,line
        if match[1].upper() not in aliases:rows.append(line)
    filtered.write_text('\n'.join(rows)+'\n')
    assert len(rows)==174212
    filtered_values=read_bias(filtered)
    assert filtered_values=={n:v for n,v in initial_values.items() if n not in aliases}
    old_include=f'.include "{initial}"'
    assert transformed.count(old_include)==1
    transformed=transformed.replace(old_include,f'.include "{filtered.resolve()}"')
    deck=args.output/'point.cir';deck.write_text(transformed)
    save(args.output/'ground_coordinate_mapping.json',dict(aliases=aliases,removed_sources=removed,
        original_public_IC_entries=len(initial_values),remaining_IC_entries=len(rows)))
    # Revalidate all inherited source/model/binary pins; the physical netlist
    # and numerical settings are unchanged. New inputs are added separately.
    pins=prior['input_sha256'].copy()
    assert all(digest(Path(name))==value for name,value in pins.items())
    for path in [Path(__file__).resolve(),Path(__file__).with_name('canonical_zero_voltage_nodes.py'),
                 Path(__file__).with_name('run_DCO_seeded_C_free_DC.py'),controls,prior_manifest,original,filtered,deck,
                 args.output/'ground_coordinate_mapping.json']:
        pins[str(path.resolve())]=digest(path)
    save(args.output/'input_manifest.json',dict(input_sha256=pins,parameters=params,
        physical_candidate_and_R_C_device_cards_byte_identical=True,
        external_constant_zero_sources_eliminated=296,physical_wire_nodes_eliminated=0,
        physical_state_approximation=False,initial_voltages_changed=False,
        linear_solver='KLU',simulator='upstream Xyce7.10',matrix_partitioning=False,
        expected_unknowns=174551,original_unknowns=175143,
        original_deadline_uptime=deadline,identical_native_retry=False,budget_restarted=False))
    binary=Path('/opt/xyce/bin/Xyce');proc=Path('/proc')/str(args.replace_native_pid)
    argv=[v.decode() for v in (proc/'cmdline').read_bytes().split(b'\0') if v]
    assert argv==[str(binary),'-quiet','-o',str(original.resolve()),str(original.resolve())]
    assert os.getpgid(args.replace_native_pid)==args.replace_native_pid
    wave=args.prior/'point.cir.prn'
    observed=[]
    if wave.exists():
        for line in wave.read_text().splitlines()[1:]:
            tokens=line.split()
            if len(tokens)==4:observed.append(float(tokens[1]))
    if observed and max(observed)>0:
        status('replacement_deferred_prior_transient_has_progress',prior_max_time_s=max(observed))
        return
    stopped=args.prior/'stopped_for_exact_ground_coordinate_change.json'
    assert not stopped.exists()
    save(stopped,dict(pid=args.replace_native_pid,argv=argv,proc_stat=(proc/'stat').read_text(),
        reason='Native controls validate exact elimination of known-zero external constraints; physical candidate and initial voltages remain unchanged',
        old_deck_sha256=digest(original),new_deck=str(deck.resolve()),new_deck_sha256=digest(deck),
        complete_preparation_manifest=str((args.output/'input_manifest.json').resolve()),
        physical_approximation=False,budget_restarted=False,identical_native_retry=False,deadline_uptime=deadline))
    os.killpg(args.replace_native_pid,signal.SIGTERM)
    end=time.monotonic()+10
    while proc.exists():
        try:
            if (proc/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':break
        except FileNotFoundError:break
        assert time.monotonic()<end,'Prior large native instance did not stop'
        time.sleep(.1)
    while True:
        assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            active=live_engines()
            if len(active)<4:
                with (args.output/'native.log').open('x') as log:
                    child=subprocess.Popen([str(binary),'-quiet','-o',str(deck.resolve()),str(deck.resolve())],
                        cwd='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice',
                        stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
                status('native_canonical_ground_point_running',native_pid=child.pid,previous_engines=active)
                break
        time.sleep(1)
    try:code=child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);child.wait()
        status('timeout_inconclusive');return
    output=Path(str(deck)+'.prn');metrics=None
    if code==0 and output.exists():
        records=[line.split() for line in output.read_text().splitlines()[1:] if len(line.split())==4]
        assert all(int(row[0])==i for i,row in enumerate(records))
        ts=[float(row[1]) for row in records];vs=[float(row[2]) for row in records]
        assert all(math.isfinite(v) for v in ts+vs) and ts[-1]>=params['duration_ns']*1e-9*(1-1e-7)
        edges=[]
        for i in range(1,len(ts)):
            if vs[i-1]<.9<=vs[i]:
                t=ts[i-1]+(.9-vs[i-1])*(ts[i]-ts[i-1])/(vs[i]-vs[i-1])
                if t>=params['measure_start_ns']*1e-9:edges.append(t)
        if len(edges)>=4:metrics=dict(mhz=(len(edges)-1)/(edges[-1]-edges[0])*1e-6,periods=len(edges)-1,
            output_min_V=min(vs),output_max_V=max(vs))
    assert all(digest(Path(name))==value for name,value in pins.items())
    artifacts=[path for path in args.output.iterdir() if path.is_file() and path.name not in ['status.json','assessment.json']]
    save(args.output/'assessment.json',dict(native_exit=code,metrics=metrics,
        completed_diagnostic_oscillation=metrics is not None,exact_ground_coordinate_transformation=True,
        physical_model_approximated=False,physical_wire_nodes_eliminated=0,
        source_model_convention_and_frequency_convergence_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256=pins,artifacts={str(p.resolve()):digest(p) for p in artifacts}))
    status('completed' if metrics else 'native_or_oscillation_nonpass',native_exit=code,metrics=metrics)
    print(json.dumps(dict(native_exit=code,metrics=metrics)))


if __name__=='__main__':main()
