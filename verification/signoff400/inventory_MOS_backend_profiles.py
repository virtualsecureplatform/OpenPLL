"""Inventory every native MOS parameter alternative without selecting junction areas."""
import argparse,json,time
from pathlib import Path
from collections import Counter
from common import save,sha
from resources import lease


def run(out):
    out.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/signoff400';proof=base/'startup_timing_native_device_provenance_001/assessment.json';a=json.loads(proof.read_text());ledger=proof.parent/'native_device_provenance.jsonl';requirements=root/'verification/signoff400/requirements.json';spec=json.loads(requirements.read_text());paths=[proof,ledger,requirements,Path(__file__).resolve()];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(1,2,deadline):
        pins={str(p):sha(p) for p in paths}
        if pins[str(ledger)]!=a['artifacts'][str(ledger)]:raise ValueError('audited current native device ledger changed')
        pool={};devices=Counter();geometries=set();changes=set();phase_counts=Counter()
        with ledger.open() as stream:
            for line in stream:
                if 'fet_' not in line:continue
                r=json.loads(line);model=r['model']
                if 'fet_' not in model:continue
                if r['native_terminal_order']!=[3,1,2,4]:raise ValueError('complete native MOS terminal order required')
                devices[model]+=1
                if r['unresolved_parameter_differences']:changes.add(r['instance'])
                for phase in ('pre_R','post_R'):
                    params=r[phase+'_parameters']
                    if not {'w','l'}<=params.keys():raise ValueError('explicit native geometry required')
                    key=(model,tuple(sorted(params.items())));geometries.add((model,params['w'],params['l']));phase_counts[phase]+=1
                    if key not in pool:pool[key]=dict(model=model,parameters=params,native_instance_phases=[],unresolved_native_instances=[])
                    pool[key]['native_instance_phases'].append(dict(instance=r['instance'],phase=phase))
                    if r['unresolved_parameter_differences']:pool[key]['unresolved_native_instances']=sorted(set(pool[key]['unresolved_native_instances']+[r['instance']]))
        if sum(devices.values())!=51525 or changes!={'X14','X52'}:raise ValueError('exact current MOS inventory and unresolved alternatives required')
        ordered=sorted(pool);priority=[]
        # Keep both unresolved alternatives and every model family in the first
        # controlled batch; the complete plan still includes every profile.
        for key in ordered:
            if pool[key]['unresolved_native_instances']:priority.append(key)
        for model in sorted(devices):
            candidates=[k for k in ordered if k[0]==model];key=max(candidates,key=lambda k:len(pool[k]['native_instance_phases']))
            if key not in priority:priority.append(key)
        keys=priority+[k for k in ordered if k not in priority];target=out/'profiles.jsonl';rows=[]
        for i,key in enumerate(keys):rows.append(dict(profile_id=i,**pool[key],physical_junction_parameter_set_selected=False))
        with target.open('x') as f:
            for row in rows:f.write(json.dumps(row)+'\n')
        per_model=Counter(row['model'] for row in rows);coverage=out/'model_coverage.json';save(coverage,{model:dict(native_instances=count,unique_full_parameter_profiles=per_model[model],unique_W_L_pairs=sum(m==model for m,w,l in geometries)) for model,count in devices.items()})
        grid=dict(required_PVT=[dict(corner=c,temperature_c=t,supply_v=1.8) for c in spec['corners'] for t in spec['temperatures_c']],DC_gate_sweep_v=[0,1.8,.3],drain_source_bias_magnitudes_v=[0,.9,1.8],reverse_body_bias_magnitudes_v=[0,.2],AC_gate_source_bias_magnitudes_v=[0,.9,1.8],AC_terminal_excitations=['gate','drain','bulk'],AC_frequencies_hz=[1e6,4e8],profile_batch_size=16,analyses=['dc','ac'],comparison_scope='finite bias grid only; no response enclosure or physical device-area selection')
        plan=out/'comparison_plan.json';save(plan,grid)
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('profile inventory source changed')
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (target,coverage,plan)},native_MOS_instances=sum(devices.values()),native_model_families=len(devices),full_parameter_profiles=len(rows),unique_model_W_L_pairs=len(geometries),instance_phase_observations=dict(phase_counts),both_unresolved_parameter_alternatives_preserved=True,unresolved_devices=sorted(changes),all_native_MOS_profile_parameters_preserved=True,native_simulations_started=0,finite_grid_is_not_domain_enclosure=True,physical_junction_parameter_set_selected=False,MOS_backend_compatibility_qualified=False,release_qualified=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
