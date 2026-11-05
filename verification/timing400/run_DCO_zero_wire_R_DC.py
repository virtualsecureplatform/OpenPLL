#!/usr/bin/env python3
"""DC-only ideal-wire diagnostic for bias conditioning and possible node seeds.

Native nonlinear devices and their parameters are unchanged. Only the finite
wire-R domain is collapsed onto its original proven conductor components.
This never qualifies finite-R DC, dynamic charge, frequency or a runtime model.
"""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines,model_files


def main():
    root=Path(__file__).resolve().parents[2]
    base=root/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    family=base/'DCO_complete_domain_model_primitives_001'
    boundary=base/'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
    topology=base/'DCO_DC_constraint_topology_001/assessment.json'
    assert json.loads(topology.read_text())['each_original_conductor_has_exactly_one_R_component']
    originals={r['private_id']:r['original_conductor'] for r in json.loads((family/'nodes.json').read_text())}
    names=sorted(set(originals.values()))
    assert len(names)==2686
    public={}
    for row in json.loads(boundary.read_text()):
        net=originals[row['private_node']]
        assert public.get(net,row['public_port'])==row['public_port']
        public[net]=row['public_port']
    assert len(public)==308
    aliases={n:public.get(n,f'_dcwire_{i}') for i,n in enumerate(names)}
    assert len(set(aliases.values()))==len(names)
    candidate_proof=base/'DCO_domain_candidate_nom_001/assessment.json'
    ports=json.loads(candidate_proof.read_text())['public_port_names']
    assert set(ports)==set(public.values())
    out=base/'DCO_domain_nom_tt27_c0_f247_zero_wire_R_DC_001'
    out.mkdir(exist_ok=False)
    def status(state,**more):
        save(out/'status.json',dict(state=state,runner_pid=os.getpid(),deadline_uptime=deadline,**more))
    status('preparing_zero_wire_R_DC_only_diagnostic')
    model=out/'zero_wire_R_DC_only.spice'
    connections=json.loads((family/'device_connections.json').read_text())
    source=family/'devices_unqualified.spice'
    family_proof=json.loads((family/'assessment.json').read_text())
    assert digest(source)==family_proof['artifacts'][str(source.resolve())]
    subckt='OpenPLL_DCO_zero_wire_R_DC_only'
    count=0
    with model.open('x') as stream:
        stream.write('* Ideal-wire DC diagnostic only. Native nonlinear device cards retained.\n.subckt '+subckt+'\n')
        for i in range(0,len(ports),8):stream.write('+ '+' '.join(ports[i:i+8])+'\n')
        for line in source.read_text().splitlines():
            if not line or line.startswith('*'):continue
            tokens=line.split()
            row=connections[tokens[0]]
            terminals=row['private_terminals']
            assert tokens[1:1+len(terminals)]==terminals
            rewritten=tokens[:]
            rewritten[1:1+len(terminals)]=[aliases[originals[n]] for n in terminals]
            assert rewritten[1+len(terminals):]==tokens[1+len(terminals):]
            stream.write(' '.join(rewritten)+'\n')
            count+=1
        stream.write('.ends '+subckt+'\n')
    assert count==8620
    save(out/'original_conductor_aliases.json',aliases)
    prior=base/'DCO_domain_nom_tt27_c0_f247_C_free_DC_001/point.cir'
    prior_model=prior.parent/'C_free_DC_only.spice'
    deck=out/'point.cir'
    old=prior.read_text()
    replacements={f'.include "{prior_model.resolve()}"':f'.include "{model.resolve()}"',
        'OpenPLL_DCO_domain_nom__ideal_point_feeds':subckt,
        f'.SAVE TYPE=IC FILE={prior.parent.resolve()}/operating.ic':f'.SAVE TYPE=IC FILE={out.resolve()}/operating.ic'}
    for a,b in replacements.items():
        assert old.count(a)==1,a
        old=old.replace(a,b)
    deck.write_text(old)
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice')
    binary=Path('/opt/xyce/bin/Xyce')
    inputs=[Path(__file__).resolve(),owner,boundary,topology,candidate_proof,source,
        family/'nodes.json',family/'device_connections.json',family/'assessment.json',prior,model,deck,binary,
        *model_files(pdk/'sky130.lib.spice',deadline)]
    pins={str(p.resolve()):digest(p) for p in inputs}
    save(out/'input_manifest.json',dict(input_sha256=pins,wire_R_collapsed_for_DC_diagnosis_only=True,
        native_devices_unchanged_except_conductor_aliases=8620,original_conductors=2686,
        no_capacitor_or_dynamic_simulation=True,identical_native_retry=False,budget_restarted=False))
    while True:
        assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
        with (base.parent/'guarded_native_admission.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            active=live_engines()
            if len(active)<4:
                with (out/'native.log').open('x') as log:
                    child=subprocess.Popen([str(binary),'-quiet','-o',str(deck.resolve()),str(deck.resolve())],
                        cwd=pdk,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
                status('native_zero_wire_R_DC_running',native_pid=child.pid,previous_engines=active)
                break
        time.sleep(1)
    try:
        code=child.wait(timeout=deadline-time.clock_gettime(time.CLOCK_BOOTTIME))
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL)
            child.wait()
        status('timeout_inconclusive')
        return
    bias=out/'operating.ic'
    passed=code==0 and bias.exists() and bias.stat().st_size>0
    assert all(digest(Path(p))==v for p,v in pins.items())
    artifacts=[p for p in out.iterdir() if p.is_file() and p.name not in ['status.json','assessment.json']]
    save(out/'assessment.json',dict(native_exit=code,zero_wire_R_DC_diagnostic_completed=passed,
        finite_R_DC_or_startup_qualified=False,frequency_or_calibration_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256=pins,artifacts={str(p.resolve()):digest(p) for p in artifacts}))
    status('completed' if passed else 'native_zero_wire_R_DC_nonpass',native_exit=code)
    print(json.dumps(dict(native_exit=code,zero_wire_R_DC_completed=passed)))


if __name__=='__main__':main()
