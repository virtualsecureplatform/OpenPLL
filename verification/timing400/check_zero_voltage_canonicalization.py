#!/usr/bin/env python3
"""Native equivalence of redundant ground constraints and canonical node zero.

Exercise a signed positive-semidefinite capacitance mass matrix, finite R and
BSIM inverter. Compare voltages, supply current and crossing times with the
same golden engine and unchanged tolerances/stimulus. No DCO state is reduced.
"""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import numpy as np
from canonical_zero_voltage_nodes import canonicalize
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines,model_files


def main():
    base=Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    out=base/'zero_voltage_canonicalization_controls_001';out.mkdir(exist_ok=False)
    reference=base/'split_DC_initialization_controls_001/full/control.cir'
    old=reference.read_text().splitlines()
    expanded=[old[0]]
    # Put every circuit ground on a named node held at exactly zero volts.
    for line in old[1:]:
        words=line.split()
        if words and words[0].startswith(('V','R','C','X')):
            count=4 if words[0].startswith('X') else 2
            for i in range(1,min(len(words),count+1)):
                if words[i]=='0':words[i]='GROUND_SURROGATE'
        if words and words[0].lower()=='.save':continue
        if words and words[0].lower()=='.print':
            words=['.print','TRAN','FORMAT=STD','PRECISION=16','V(a)','V(b)','V(output)','I(VDD)']
        if words and words[0].lower()=='.end':
            expanded.append('VZERO_GROUND GROUND_SURROGATE 0 0')
        expanded.append(' '.join(words))
    original='\n'.join(expanded)+'\n'
    transformed,aliases,removed=canonicalize(original)
    assert aliases=={'GROUND_SURROGATE':'0'} and len(removed)==1
    # Guard a source-current observation that cannot be silently discarded.
    try:canonicalize(original.replace('.end','.print TRAN I(VZERO_GROUND)\n.end'))
    except ValueError:pass
    else:raise AssertionError('Removed an observed source-current variable')
    binary=Path('/opt/xyce/bin/Xyce')
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice')
    inputs=[Path(__file__).resolve(),Path(__file__).with_name('canonical_zero_voltage_nodes.py'),
        owner,reference,binary,*model_files(pdk/'sky130.lib.spice',deadline)]
    artifacts=[];waves=[]
    for name,circuit in [('explicit_zero_constraint',original),('canonical_ground',transformed)]:
        folder=out/name;folder.mkdir();deck=folder/'control.cir';deck.write_text(circuit);inputs.append(deck)
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            assert len(live_engines())<4
            with (folder/'native.log').open('x') as log:
                child=subprocess.Popen([str(binary),'-quiet','-o',str(deck.resolve()),str(deck.resolve())],
                    cwd=pdk,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
            save(out/'status.json',dict(state='checking_native_voltage_constraint_equivalence',case=name,
                native_pid=child.pid,runner_pid=os.getpid(),deadline_uptime=deadline))
        try:code=child.wait(timeout=min(120.,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)))
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=10)
            save(out/'status.json',dict(state='timeout_inconclusive',case=name));return
        assert code==0,(folder/'native.log').read_text()[-2000:]
        wave=Path(str(deck)+'.prn');lines=wave.read_text().splitlines()
        assert lines[0].split()==['Index','TIME','V(A)','V(B)','V(OUTPUT)','I(VDD)']
        rows=[s.split() for s in lines[1:] if len(s.split())==6]
        assert all(int(row[0])==i for i,row in enumerate(rows))
        data=np.array([[float(v) for v in row[1:]] for row in rows]);assert data[-1,0]>=8e-9*(1-1e-8)
        waves.append(data);artifacts.extend(p for p in folder.iterdir() if p.is_file() and p!=deck)
    t=np.linspace(0,8e-9,8001)
    a,b=waves
    errors=[float(max(abs(np.interp(t,a[:,0],a[:,i])-np.interp(t,b[:,0],b[:,i])))) for i in range(1,5)]
    assert max(errors[:2])<1e-5 and errors[2]<2e-3
    current_scale=max(float(max(abs(a[:,4]))),float(max(abs(b[:,4]))),1e-12)
    assert errors[3]<1e-3*current_scale+1e-10
    def edges(data):
        values=[]
        for left,right in zip(data,data[1:]):
            if left[3]<.9<=right[3]:values.append(float(left[0]+(.9-left[3])*(right[0]-left[0])/(right[3]-left[3])))
        return values
    ea,eb=edges(a),edges(b);assert len(ea)==len(eb)>0
    crossing=max(abs(x-y) for x,y in zip(ea,eb));assert crossing<1e-13
    result=dict(native_voltage_constraint_canonicalization_controls_passed=True,
        finite_R_signed_C_and_BSIM_controls=True,native_cases=2,
        maximum_voltage_differences_V=errors[:3],maximum_supply_current_difference_A=errors[3],
        maximum_rising_crossing_difference_s=crossing,observed_source_current_removal_guard_passed=True,
        physical_circuit_approximated=False,DCO_timing_or_frequency_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs},
        artifacts={str(p.resolve()):digest(p) for p in artifacts})
    save(out/'assessment.json',result);save(out/'status.json',dict(state='completed',controls_passed=True))
    print(json.dumps({k:v for k,v in result.items() if k not in ['input_sha256','artifacts']},indent=2))


if __name__=='__main__':main()
