"""Exact symbolic charge reduction of prescribed capacitor-only boundary ports."""
import argparse,hashlib,json,os,time
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from audit_keeper_native_R_contraction import number


def decimal_exact(value):
    denominator=value.denominator;a=b=0
    while denominator%2==0:denominator//=2;a+=1
    while denominator%5==0:denominator//=5;b+=1
    if denominator!=1:raise ValueError('finite decimal capacitance required')
    digits=max(a,b);numerator=value.numerator*2**(digits-a)*5**(digits-b);sign='-' if numerator<0 else '';s=str(abs(numerator)).rjust(digits+1,'0')
    return sign+(s[:-digits]+'.'+s[-digits:] if digits else s)


def root_info(text):
    lines=text.splitlines(keepends=True);header=end=None;active=False;body=[]
    for i,line in enumerate(lines):
        f=line.split()
        if not f or f[0].startswith('*'):continue
        if f[0].lower()=='.subckt':
            if active:raise ValueError('nested conditional root')
            if not f[1].startswith('__openpll_'):
                if header is not None:raise ValueError('one conditional root required')
                header=i;active=True
        elif f[0].lower()=='.ends' and active:end=i;active=False
        elif active:
            if f[0][0].upper() not in ['X','R','C']:raise ValueError('unsupported conditional root card')
            body.append((i,f))
    if header is None or end is None or active:raise ValueError('complete conditional root required')
    return lines,header,end,body


def protected_digest(text):
    lines,header,end,body=root_info(text);caps={i for i,f in body if f[0][0].upper()=='C'}
    return hashlib.sha256(''.join(line for i,line in enumerate(lines) if i!=header and i not in caps and line.strip() and not line.lstrip().startswith('*')).encode()).hexdigest()


def transform(text,bindings):
    lines,header,end,body=root_info(text);external={v.lower():k for k,v in bindings['externally_driven_ports'].items()};observed={v.lower() for v in bindings['observation_only_ports'].values()};ports=lines[header].split()[2:];external_set=set(external);forced=external_set|{'0'}
    if len(external)!=len(bindings['externally_driven_ports']) or set(external)&observed or {p.lower() for p in ports}!=set(external)|observed or len(ports)!=len(external)+len(observed):raise ValueError('complete unique prescribed/observed root interface required')
    direct=set();tokens={w.lower() for _,f in body for w in f}|{p.lower() for p in ports};names={f[0].lower() for _,f in body}
    for _,f in body:
        if f[0][0].upper()!='C':direct.update({w.lower() for w in f[1:]}&external_set)
    eliminated=set(external)-direct;groups=defaultdict(lambda:defaultdict(F));removed=set();discarded=grouped=0
    for i,f in body:
        if f[0][0].upper()!='C':continue
        if len(f)!=4:raise ValueError('literal two-terminal C required')
        a,b=f[1].lower(),f[2].lower();value=number(f[3])
        if value<=0:raise ValueError('positive constant C required')
        if not {a,b}&eliminated:continue
        removed.add(i)
        if a in forced and b in forced:discarded+=1
        else:
            inner=b if a in eliminated else a;boundary=a if a in eliminated else b;groups[inner][boundary]+=value;grouped+=1
    additions=[];certificate=[];new_driven={k:v for k,v in bindings['externally_driven_ports'].items() if v.lower() not in eliminated};synthetic={}
    for j,(inner,terms) in enumerate(sorted(groups.items())):
        node='openpll_cap_force_'+str(j);card='CopenpllCapAggregate'+str(j);key='CAP_AGGREGATE['+str(j)+']'
        if node in tokens or card.lower() in names or key in bindings['all_physical_nodes']:raise ValueError('aggregate node/card collision')
        total=sum(terms.values(),F(0));weights={external[n]:v/total for n,v in terms.items()}
        if sum(weights.values(),F(0))!=1 or any(total*weights[external[n]]!=v for n,v in terms.items()):raise ValueError('symbolic charge coefficient mismatch')
        literal=decimal_exact(total)
        if number(literal)!=total:raise ValueError('aggregate capacitor literal not exact')
        additions.append(card+' '+inner+' '+node+' '+literal+'\n');new_driven[key]=node;synthetic[key]=node
        certificate.append(dict(internal_native_node=inner,aggregate_physical_key=key,aggregate_native_port=node,total_capacitance_F_exact=str(total),boundary_weights_exact={k:str(v) for k,v in weights.items()},original_boundary_C_F_exact={external[n]:str(v) for n,v in terms.items()}))
    root=lines[header].split()[1];new_ports=[p for p in ports if p.lower() not in eliminated]+list(synthetic.values());result=['* Symbolic prescribed-boundary C reduction; native equivalence unqualified.\n']
    for i,line in enumerate(lines):
        if i==header:result.append('.subckt '+root+' '+' '.join(new_ports)+'\n')
        elif i in removed:continue
        elif i==end:result.extend(additions);result.append(line)
        else:result.append(line)
    result=''.join(result)
    if protected_digest(result)!=protected_digest(text):raise ValueError('primitive or wrapper records changed')
    new_bindings=dict(bindings,externally_driven_ports=new_driven,all_physical_nodes={k:v for k,v in bindings['all_physical_nodes'].items() if v.lower() not in eliminated},synthetic_forcing_nodes=synthetic,eliminated_physical_nodes={external[n]:n for n in sorted(eliminated)})
    plan=dict(groups=certificate,original_primitive_calls=sum(f[0][0].upper()=='X' for _,f in body),original_explicit_C_cards=sum(f[0][0].upper()=='C' for _,f in body),transformed_explicit_C_cards=sum(f[0][0].upper()=='C' for _,f in body)-len(removed)+len(additions),eliminated_boundary_ports=len(eliminated),retained_direct_boundary_ports=len(direct),aggregate_forcing_ports=len(groups),transformed_driven_ports=len(new_driven),discarded_forced_boundary_only_C=discarded,grouped_boundary_to_interior_C=grouped,inserted_aggregate_C=len(additions),symbolic_retained_charge_coefficients_preserved=True,primitive_and_wrapper_records_sha256=protected_digest(text),prescribed_boundary_histories_required_unchanged=True,boundary_source_currents_preserved=False,floating_point_aggregation_error_qualified=False,native_equivalence_verified=False,native_simulation_allowed=False,model_qualified=False,release_ready=False)
    return result,new_bindings,plan


def run(conditional,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        receipt=conditional/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts']);model=conditional/'model.spice';binding=conditional/'bindings.json'
        pins={str(p):sha(p) for p in [receipt,model,binding,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_native_R_contraction.py')]};save(output/'inputs.json',dict(input_sha256=pins,memory_GiB=2,CPU=29,resource_queue_cap_s=7200,native_simulation_requested=False,release_ready=False));save(output/'status.json',dict(state='waiting_for_global_CPU_RAM_budget',release_ready=False))
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            text,new_bindings,plan=transform(model.read_text(),json.loads(binding.read_text()))
            if plan['original_primitive_calls']!=a['selected_primitive_count'] or plan['original_explicit_C_cards']!=a['nonzero_C_endpoints_and_values_exactly_preserved']:raise ValueError('source model inventory differs from checked conditional receipt')
            target=output/'model.spice';target.write_text(text);save(output/'bindings.json',new_bindings);save(output/'charge_certificate.json',plan);verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [target,output/'bindings.json',output/'charge_certificate.json']},**{k:v for k,v in plan.items() if k!='groups'},source_primitive_count=a['selected_primitive_count'],source_nonzero_C_cards=a['nonzero_C_endpoints_and_values_exactly_preserved']));save(output/'status.json',dict(state='symbolic_boundary_reduction_complete_native_unqualified',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['conditional','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.conditional.resolve(),a.output.resolve())
