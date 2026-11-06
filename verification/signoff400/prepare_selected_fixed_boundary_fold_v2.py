"""Prepare an affine fixed-boundary reduction of a frozen conditional native cut."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from audit_selected_dco_history_inputs import sources
from fold_fixed_voltage_passives_v2 import fold
from certify_selected_cut_C_passivity import projected_pairs
from certify_prototype_parallel_C_paths_v2 import certificate,replay


def top_nodes(text):
    result=set();depth=0
    for line in text.splitlines():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':depth+=1;continue
        if f[0].lower()=='.ends':depth-=1;continue
        if depth:continue
        if f[0].startswith('Xflat'):
            stop=next(i for i,t in enumerate(f)if t.startswith('__openpll_literal_leaf_'));result.update(f[1:stop])
        elif f[0][0].upper()in ('R','C','I'):result.update(f[1:3])
    return result


def run(baseline,plan,passivity,output):
    os.sched_setaffinity(0,{22});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_affine_fixed_boundary_fold',release_ready=False))
    try:
        manifest=baseline/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
        p=json.loads(plan.read_text());verify(p['input_sha256'])
        if m['input_sha256'].get(str(plan))!=sha(plan):raise ValueError('same physical cut plan required')
        devices=baseline/'devices.spice';src=baseline/'sources.spice'
        for path in (devices,src):
            if m['input_sha256'].get(str(path))!=sha(path):raise ValueError('frozen original native input required')
        prior=json.loads(passivity.read_text());verify(prior['input_sha256']);verify(prior['artifacts'])
        if not prior['actual_cut_free_linear_C_passivity_certified']:raise ValueError('passing actual cut C certificate required')
        for path in (devices,src):
            if prior['input_sha256'].get(str(path))!=sha(path):raise ValueError('passivity certificate applies to another cut')
        files=[passivity,manifest,plan,devices,src,baseline/'initial_conditions.spice',Path(__file__).resolve()]
        files += [Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','audit_selected_dco_history_inputs.py','audit_hierarchical_capacitance.py','fold_fixed_voltage_passives_v2.py','certify_selected_cut_C_passivity.py','certify_prototype_parallel_C_paths_v2.py')]
        pins={str(x):sha(x)for x in files};verify(pins)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
        with lease(1,4,deadline):
            original_pairs,_=projected_pairs(devices.read_text(),set(sources(src))|{'0'})
            old_proof=passivity.parent/'proof.json'
            if prior['artifacts'].get(str(old_proof))!=sha(old_proof):raise ValueError('source energy witness not pinned')
            replay(original_pairs,json.loads(old_proof.read_text()))
            converted,new_sources,report=fold(devices.read_text(),sources(src),allow_signed_capacitors=True)
            # Private nodes must remain actual device/passive nodes, not just IC labels.
            if not set(p['private_unknown_nodes'])<=top_nodes(converted):raise ValueError('private initialized voltage node removed')
            output_devices=output/'devices.spice';output_sources=output/'sources.spice'
            output_devices.write_text(converted);output_sources.write_text(new_sources)
            serialized_pairs,_=projected_pairs(converted,set(sources(output_sources))|{'0'})
            proof=certificate(serialized_pairs);replayed=replay(serialized_pairs,proof)
            proof_path=output/'serialized_C_proof.json';save(proof_path,proof)
        verify(pins)
        artifacts={str(x):sha(x)for x in (output_devices,output_sources,proof_path)}
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,**report,
            serialized_free_C_passivity_certified=True,serialized_C_rational_witness_replay=replayed,original_native_case=str(baseline),initialized_private_nodes_preserved=len(p['private_unknown_nodes']),
            power_and_fixed_boundary_current_qualified=False))
        save(output/'status.json',dict(state='affine_fixed_boundary_fold_prepared',release_ready=False));print(json.dumps(report))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','plan','passivity','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ('baseline','plan','passivity','output')))
