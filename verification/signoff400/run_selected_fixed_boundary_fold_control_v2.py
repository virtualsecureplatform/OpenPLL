"""Run an equation-preserving fixed-boundary fold against its frozen native control.

Preserve every nonlinear definition/card, initial voltage, dynamic source and
integration setting. Only certified affine passive stamps and redundant fixed
voltage sources change. Source currents and absolute stored charge are outside
this retained-voltage experiment.
"""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from audit_selected_dco_history_inputs import sources
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def nonlinear_text(text):
    kept=[];depth=0
    for line in text.splitlines(keepends=True):
        f=line.split()
        if not f:kept.append(line);continue
        if f[0].lower()=='.subckt':depth+=1
        if f[0].lower()=='.ends':depth-=1;kept.append(line);continue
        if depth or f[0][0].upper()not in ('R','C','I'):kept.append(line)
    return ''.join(kept)


def run(baseline,folded,output,cpu=22):
    if cpu not in range(16,32):raise ValueError('spare physical core required')
    os.sched_setaffinity(0,{cpu});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_saved_state_DCO_diagnostic',release_ready=False))
    try:
        m=json.loads((baseline/'manifest.json').read_text());verify(m['input_sha256'])
        receipt=folded/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r['input_sha256'].get(str(baseline/'manifest.json'))!=sha(baseline/'manifest.json'):raise ValueError('folded case differs from original native control')
        if not r['serialized_free_C_passivity_certified'] or not r['retained_node_equations_exact_before_serialization']:raise ValueError('passing source and serialized operator checks required')
        original=(baseline/'devices.spice').read_text();new=(folded/'devices.spice').read_text()
        if nonlinear_text(original)!=nonlinear_text(new):raise ValueError('nonlinear cards or definitions changed')
        removed=set(sources(baseline/'sources.spice'))-set(sources(folded/'sources.spice'))
        tokens=set(re.split(r'[\s,(){}=:+*/]+',nonlinear_text(original).upper()))
        if {n.upper()for n in removed}&tokens:raise ValueError('removed fixed source remains referenced by nonlinear definitions')
        original_manifests=[Path(x)for x in m['input_sha256']if x.endswith('/manifest.json')]
        if len(original_manifests)!=1:raise ValueError('unique original physical model manifest required')
        binary_paths=[Path(x)for x in m['input_sha256']if x.endswith('/Xyce')]
        if len(binary_paths)!=1:raise ValueError('unique pinned native executable required')
        binary=binary_paths[0];deck=output/'control.spice';raw=output/'control.raw'
        text=(baseline/'control.spice').read_text()
        for name in ('devices.spice','sources.spice'):
            token=str(baseline/name)
            if text.count(token)!=1:raise ValueError('unique original native include required')
            text=text.replace(token,str(folded/name))
        if text.count(str(baseline/'control.raw'))!=1:raise ValueError('unique original waveform destination required')
        text=text.replace(str(baseline/'control.raw'),str(raw));deck.write_text(text)
        paths=[receipt,*map(Path,r['artifacts']),original_manifests[0],baseline/'control.spice',baseline/'initial_conditions.spice',deck,binary,Path(__file__).resolve()]
        paths += [Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','compiled_charge_v2.py','audit_selected_dco_history_inputs.py','assess_selected_detector_prefix.py','assess_selected_isolated_control.py')]
        pins={str(p):sha(p)for p in paths};verify(pins)
        fields={k:m[k]for k in ('controls','operating_point','observed_roles','native_checkpoint_time_s','simulation_end_s','original_full_reference_end_s','initialized_private_nodes','all_private_voltages_bound','DCOP_skipped','private_voltages_constrained_during_DCOP')}
        save(output/'manifest.json',dict(input_sha256=pins,CPU=cpu,MPI_ranks=1,memory_GiB=8,native_cap_s=10800,
             **fields,affine_fixed_boundary_fold_applied=True,original_native_case=str(baseline),
             original_native_case_manifest_sha256=sha(baseline/'manifest.json'),nonlinear_restart_and_boundary_charge_state_qualified=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
        save(output/'status.json',dict(state='saved_state_DCO_native_running',release_ready=False))
        with lease(1,8,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,8)
        verify(pins);rows,info=read_prefix(raw,m['observed_roles'])
        if info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-m['simulation_end_s'])>1e-18:raise ValueError('complete original native horizon required')
        measured=frequency(rows,(200e-9-m['native_checkpoint_time_s'])*1e9,m['simulation_end_s']*1e9)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(raw):sha(raw)},frequency=measured,waveform=info,
             native_fold_response_equivalence_qualified=False,nonlinear_restart_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='saved_state_DCO_diagnostic_complete',release_ready=False));print(json.dumps(measured))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','folded','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--cpu',type=int,choices=range(16,32),default=22)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ('baseline','folded','output')),a.cpu)
