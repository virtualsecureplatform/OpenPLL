"""Certify the free linear-C operator of an actual conditional native cut.

Every prescribed voltage source is projected to one AC reference. Signed
native capacitor branches are retained and aggregated exactly. Parallel-path
witnesses prove nonnegative free-node energy; no coefficient is changed.
"""
import argparse,json,os,time
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from audit_hierarchical_capacitance import number
from audit_selected_dco_history_inputs import sources
from certify_prototype_parallel_C_paths_v2 import certificate,replay


def projected_pairs(text,fixed):
    pairs=defaultdict(F);depth=0;cards=0;negative_cards=0
    for line in text.splitlines():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':depth+=1;continue
        if f[0].lower()=='.ends':depth-=1;continue
        if depth or f[0][0].upper()!='C':continue
        if len(f)!=4:raise ValueError('constant top-level C required')
        value=number(f[3]);cards+=1;negative_cards+=value<0
        a,b=[('__fixed_AC_reference'if n in fixed else n)for n in f[1:3]]
        if a!=b:pairs[tuple(sorted((a,b)))]+=value
    return dict(pairs),dict(original_C_cards=cards,original_negative_C_cards=negative_cards,projected_negative_pairs=sum(c<0 for c in pairs.values()))


def run(native,plan,output):
    os.sched_setaffinity(0,{22});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='certifying_actual_cut_free_C_operator',release_ready=False))
    try:
        manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        p=json.loads(plan.read_text());verify(p['input_sha256'])
        if m['input_sha256'].get(str(plan))!=sha(plan):raise ValueError('same actual cut plan required')
        devices=native/'devices.spice';src=native/'sources.spice'
        for path in (devices,src):
            if m['input_sha256'].get(str(path))!=sha(path):raise ValueError('actual native input not pinned')
        paths=[manifest,plan,devices,src,Path(__file__).resolve()]
        paths += [Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','audit_hierarchical_capacitance.py','audit_selected_dco_history_inputs.py','certify_prototype_parallel_C_paths_v2.py')]
        pins={str(x):sha(x)for x in paths};verify(pins)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
        with lease(1,4,deadline):
            pairs,counts=projected_pairs(devices.read_text(),set(sources(src))|{'0'})
            nodes={n for pair in pairs for n in pair}-{'__fixed_AC_reference'}
            if not nodes<=set(p['private_unknown_nodes']):raise ValueError('unclassified free capacitive node')
            path=output/'projected.pairs.jsonl'
            with path.open('x')as stream:
                for pair,value in sorted(pairs.items()):stream.write(json.dumps(dict(nodes=pair,farads=str(value)))+'\n')
            proof=certificate(pairs)
            save(output/'proof.json',proof)
            replay_result=replay(pairs,proof)if proof.get('passivity_certified')else None
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(x):sha(x)for x in (path,output/'proof.json')},
            **counts,free_capacitive_nodes=len(nodes),prescribed_voltage_nodes=len(sources(src)),
            actual_cut_free_linear_C_passivity_certified=proof.get('passivity_certified',False),
            rational_witness_replay=replay_result,no_coefficient_changed=True,
            scope='linear geometric C only, all prescribed voltage-source perturbations fixed for free-energy test',
            full_macro_dynamic_operator_qualified=False,intrinsic_device_C_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='actual_cut_free_C_passivity_assessed',release_ready=False));print(json.dumps(counts),proof.get('passivity_certified'))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('native','plan','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ('native','plan','output')))
