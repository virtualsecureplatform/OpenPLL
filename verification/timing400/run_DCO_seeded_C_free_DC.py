#!/usr/bin/env python3
"""Seed the unchanged physical-R DC problem from the completed ideal-wire bias.

NODESET changes only the initial Newton guess. It never substitutes ideal wire
values for the converged physical-R bias and never skips DC with UIC.
"""
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from compile_local_C_operators_v2 import digest,save
from run_DCO_domain_point_v3 import live_engines,model_files


def read_bias(path):
    values={}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('*'):continue
        match=re.fullmatch(r'\s*\.IC\s+V\(([^)]+)\)\s*=\s*([-+.eE0-9]+)\s*',line,re.I)
        assert match,line
        name=match[1].upper()
        assert name not in values
        value=float(match[2])
        assert math.isfinite(value)
        values[name]=value
    return values


def main():
    root=Path(__file__).resolve().parents[2]
    base=root/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    seed=base/'DCO_domain_nom_tt27_c0_f247_zero_wire_R_DC_001'
    receipt=seed/'assessment.json'
    assert json.loads(receipt.read_text())['zero_wire_R_DC_diagnostic_completed']
    aliases_path=seed/'original_conductor_aliases.json'
    aliases=json.loads(aliases_path.read_text())
    bias_path=seed/'operating.ic'
    bias=read_bias(bias_path)
    nodes_path=base/'DCO_complete_domain_model_primitives_001/nodes.json'
    nodes=json.loads(nodes_path.read_text())
    estimates={}
    for row in nodes:
        alias=aliases[row['original_conductor']].upper()
        name='XDCO:'+alias if alias.startswith('_DCWIRE_') else alias
        assert name in bias,name
        estimates['XDCO:XPHYSICAL:'+row['private_id'].upper()]=bias[name]
    assert len(estimates)==148346
    internal=0
    for name,value in bias.items():
        if name.startswith('M:XDCO:'):
            estimates[name.replace('M:XDCO:','M:XDCO:XPHYSICAL:',1)]=value
            internal+=1
    assert internal==25854
    out=base/'DCO_domain_nom_tt27_c0_f247_seeded_C_free_DC_001'
    out.mkdir(exist_ok=False)
    def status(state,**more):
        save(out/'status.json',dict(state=state,runner_pid=os.getpid(),deadline_uptime=deadline,**more))
    status('preparing_physical_R_initial_guesses')
    initial=out/'zero_wire_bias.nodeset'
    initial.write_text('* Initial guesses only; solve all actual physical-R DC equations.\n'+
        ''.join(f'.NODESET V({name}) = {value:.17g}\n' for name,value in sorted(estimates.items())))
    prior=base/'DCO_domain_nom_tt27_c0_f247_C_free_DC_001/point.cir'
    reduced=prior.parent/'C_free_DC_only.spice'
    prior_manifest=prior.parent/'input_manifest.json'
    pins_prior=json.loads(prior_manifest.read_text())['input_sha256']
    assert digest(reduced)==pins_prior[str(reduced.resolve())]
    prior_text=prior.read_text()
    old_save=f'.SAVE TYPE=IC FILE={prior.parent.resolve()}/operating.ic'
    new_save=f'.SAVE TYPE=IC FILE={out.resolve()}/operating.ic'
    assert prior_text.count(old_save)==1 and prior_text.count('.end\n')==1
    text=prior_text.replace(old_save,new_save).replace('.end\n',f'.include "{initial.resolve()}"\n.end\n')
    # Assert every original physical equation and solver option is unchanged.
    assert text.replace(new_save,old_save).replace(f'.include "{initial.resolve()}"\n','')==prior_text
    assert 'UIC' not in text
    deck=out/'point.cir'
    deck.write_text(text)
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice')
    binary=Path('/opt/xyce/bin/Xyce')
    inputs=[Path(__file__).resolve(),owner,receipt,aliases_path,bias_path,nodes_path,prior,reduced,prior_manifest,initial,deck,binary,
        *model_files(pdk/'sky130.lib.spice',deadline)]
    pins={str(p.resolve()):digest(p) for p in inputs}
    save(out/'input_manifest.json',dict(input_sha256=pins,physical_R_initial_guesses=len(nodes),
        BSIM_internal_initial_guesses=internal,actual_physical_DC_equations_unchanged=True,
        wire_R_branches_preserved=166286,UIC_used=False,initialization_changed_to_NODESET=True,
        identical_native_retry=False,budget_restarted=False))
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
                status('native_seeded_physical_R_DC_running',native_pid=child.pid,previous_engines=active)
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
    operating=out/'operating.ic'
    passed=code==0 and operating.exists() and operating.stat().st_size>0
    delta=None
    if passed:
        solved=read_bias(operating)
        assert estimates.keys()<=solved.keys()
        delta=max(abs(solved[n]-value) for n,value in estimates.items())
    assert all(digest(Path(p))==v for p,v in pins.items())
    artifacts=[p for p in out.iterdir() if p.is_file() and p.name not in ['status.json','assessment.json']]
    save(out/'assessment.json',dict(native_exit=code,seeded_physical_R_DC_completed=passed,
        physical_DC_equations_unchanged=True,maximum_solved_voltage_change_from_ideal_wire_guess_V=delta,
        full_C_DC_equivalence_or_transient_startup_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256=pins,artifacts={str(p.resolve()):digest(p) for p in artifacts}))
    status('completed' if passed else 'native_seeded_DC_nonpass',native_exit=code)
    print(json.dumps(dict(native_exit=code,seeded_physical_R_DC_completed=passed,maximum_bias_change_V=delta)))


if __name__=='__main__':main()
