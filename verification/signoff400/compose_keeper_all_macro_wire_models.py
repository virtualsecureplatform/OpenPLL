"""Assemble full parent C with fresh parent wire R; retain diagnostic C choices."""
import argparse,json,re,os,time,sys
from pathlib import Path
from common_v3 import save,sha,verify
from build_prototype_full_C_wire_R_v11 import build,rows
from compiled_charge_v2 import execute
from prepare_prototype_analog_reference import subcircuits
from bind_keeper_parent_DCO_wire import TOP as DCO
from resources import lease,identity


def worker(extraction,rc,binding,macro,bbpd,digital,output):
    receipts=[p/'assessment.json'for p in [extraction,rc,binding,macro,bbpd,digital]];records=[json.loads(p.read_text())for p in receipts]
    for r in records:verify(r['input_sha256']);verify(r['artifacts'])
    e,r,b,*macros=records
    macro_sources=[(DCO,macro,macros[0]),('IntegerPLL_BBPD',bbpd,macros[1]),('IntegerPLL_ProgrammedCore',digital,macros[2])]
    for _,_,m in macro_sources:
        if not m['exact_parent_macro_port_order_preserved']or not m['parent_extracted_macro_C_retained']or not all(x['zero_wire_R_exact_device_topology_and_C_operator_match']for x in m['results']):raise ValueError('exact parent macro interface/C preservation required')
    if not b['full_C_hierarchy_bound_to_fresh_parent_wire']:raise ValueError('complete direct full-C terminal binding required')
    if b['input_sha256'].get(str(receipts[0]))!=sha(receipts[0])or b['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):raise ValueError('C/wire binding mismatch')
    raw=next(extraction.glob('*/capacitance.spice'));joins=[Path(p)for p in b['input_sha256']if p.endswith('/join.json')]
    if len(joins)!=1:raise ValueError('one independently verified placement join required')
    join=joins[0];mapping={re.sub(r'\\(.)',r'\1',x['routed_instance']):x['extracted_instance']for x in json.loads(join.read_text())['mapping']}
    parsed=rc/'nom.json'
    if r['artifacts'].get(str(parsed))!=sha(parsed):raise ValueError('wire view changed')
    folder=Path(__file__).resolve().parent;files=[*receipts,raw,join,parsed,Path(__file__).resolve(),folder/'build_prototype_full_C_wire_R_v11.py'];pins={str(p):sha(p)for p in files};artifacts={};results=[]
    text=raw.read_text();blocks=subcircuits(text);spef=json.loads(parsed.read_text())
    if any(m['input_sha256'].get(str(raw))!=sha(raw)for _,_,m in macro_sources):raise ValueError('macro source hierarchy differs')
    for attachment in ['driver','farthest']:
        save(output/'status.json',dict(state='assembling_parent_wire_'+attachment,release_ready=False))
        nested=text
        for name,directory,m in macro_sources:
            replacement=directory/(attachment+'.spice');pins[str(replacement)]=sha(replacement)
            if m['artifacts'].get(str(replacement))!=sha(replacement):raise ValueError('macro model changed')
            patch=subcircuits(replacement.read_text())
            if set(patch)!={name}or nested.count(blocks[name])!=1:raise ValueError('one exact macro substitution required')
            if rows(patch[name])[0].split()[2:]!=rows(blocks[name])[0].split()[2:]:raise ValueError('macro interface differs')
            nested=nested.replace(blocks[name],patch[name],1)
        check=subcircuits(nested);replaced={name for name,_,_ in macro_sources}
        if set(check)!=set(blocks)or any(check[n]!=block for n,block in blocks.items()if n not in replaced):raise ValueError('non-macro hierarchy modified')
        source=output/(attachment+'.hierarchy.spice');source.write_text(nested);artifacts[str(source)]=sha(source)
        model,metrics,lift=build(nested,raw.parent.name,spef,mapping,attachment)
        if metrics['existing_positive_resistors_retained']!=17213:raise ValueError('all three macro nominal wire resistors must survive')
        target=output/(attachment+'.spice');target.write_text(model);node_map=metrics.pop('emitted_node_map');detail=output/(attachment+'.nodes.json');save(detail,dict(emitted_node_map=node_map,root_C_voltage_map=lift));artifacts.update({str(p):sha(p)for p in [target,detail]});results.append(metrics)
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,full_parent_C_retained=True,parent_wire_R_inserted=True,SPEF_C_added=False,DCO_internal_wire_R_inserted=True,BBPD_internal_wire_R_inserted=True,digital_internal_wire_R_inserted=True,standard_cell_internal_wire_R_included=False,exact_zero_all_inserted_R_parent_recovery_by_composition=True,physical_C_placement_qualified=False,emitted_operator_passivity_qualified=False,parent_loading_complete=False,native_simulation_allowed=False,release_ready=False))
    save(output/'status.json',dict(state='parent_wire_diagnostic_models_complete',release_ready=False))


def run(extraction,rc,binding,macro,bbpd,digital,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=16))
    try:
        with lease(1,16,deadline):execute([sys.executable,Path(__file__).resolve(),'--extraction',extraction,'--rc',rc,'--binding',binding,'--macro',macro,'--bbpd',bbpd,'--digital',digital,'--output',output,'--worker'],output/'native.log',deadline,16)
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['extraction','rc','binding','macro','bbpd','digital','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--worker',action='store_true');a=p.parse_args();(worker if a.worker else run)(*(getattr(a,n).resolve()for n in ['extraction','rc','binding','macro','bbpd','digital','output']))
