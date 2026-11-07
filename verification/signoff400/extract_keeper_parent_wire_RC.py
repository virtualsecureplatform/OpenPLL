"""Extract RCX views from the exact fresh route behind the checked filled parent."""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from prototype_spef_v2 import parse
from extract_prototype_parent_spef_v2 import check_network,OPENROAD
from resources import identity,lease
from compiled_charge import execute


def run(route,layout,output):
    rr=route/'assessment.json';lr=layout/'assessment.json';vr=layout/'lvs_proof/assessment.json'
    r,l,v=[json.loads(p.read_text())for p in [rr,lr,vr]]
    for record in [r,l,v]:verify(record['input_sha256']);verify(record['artifacts'])
    stream=Path(l['current_macro_sources_from_parent_stream']);s=json.loads(stream.read_text());verify(s['input_sha256']);verify(s['artifacts'])
    if l['input_sha256'].get(str(stream))!=sha(stream)or s['input_sha256'].get(str(rr))!=sha(rr):raise ValueError('checked filled parent uses another route')
    if not l['assembled_drc_pass']or not v['assembled_lvs_pass']or not v['all_three_macros_expanded']or v['input_sha256'].get(str(lr))!=sha(lr):raise ValueError('same expanded parent DRC/LVS required')
    if r['router_drc_violations']!=0 or not r['buffered_control_macro_bindings_verified']:raise ValueError('fresh checked parent route required')
    db=route/'route.odb';wires=route/'signal_wires.tsv';names={re.sub(r'\\(.)',r'\1',line)for line in wires.read_text().splitlines()}
    if not names:raise ValueError('signal route inventory missing')
    rules=ROOT/'build/timing450/pdk/sky130A/libs.tech/librelane'
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    os.sched_setaffinity(0,{24,25,26,27});os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    pins={str(p):sha(p)for p in [Path(__file__).resolve(),Path(__file__).with_name('extract_prototype_parent_spef_v2.py'),Path(__file__).with_name('prototype_spef_v2.py'),rr,lr,vr,stream,db,wires,OPENROAD]}
    artifacts={};results=[]
    try:
        for corner in ['min','nom','max']:
            model=rules/f'rules.openrcx.sky130A.{corner}.magic';pins[str(model)]=sha(model)
            target=output/(corner+'.spef');script=output/(corner+'.tcl')
            script.write_text(f'read_db {{{db}}}\nset_thread_count 4\ndefine_process_corner -ext_model_index 0 RCX_{corner.upper()}\nextract_parasitics -ext_model_file {{{model}}} -corner 0\nwrite_spef {{{target}}}\nexit\n')
            pins[str(script)]=sha(script);verify(pins);save(output/'inputs.json',dict(input_sha256=pins))
            save(output/'status.json',dict(state='extracting_keeper_parent_'+corner,release_ready=False))
            with lease(4,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/(corner+'.log'),deadline,8)
            parsed=parse(target.read_text());found={re.sub(r'\\(.)',r'\1',n['name'])for n in parsed['nets']}
            if found!=names or not parsed['pin_capacitance_excluded']:raise ValueError('SPEF route inventory or capacitance scope differs')
            networks=[check_network(n)for n in parsed['nets']];detail=output/(corner+'.json');save(detail,parsed)
            results.append(dict(corner=corner,nets=len(networks),terminals=sum(x['terminals']for x in networks),resistors=sum(x['resistors']for x in networks),capacitors=sum(x['capacitors']for x in networks)))
            artifacts.update({str(p):sha(p)for p in [target,detail,output/(corner+'.log')]})
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,parent_wire_views=['min','nom','max'],routed_signal_nets=len(names),
            all_wire_terminals_resistively_connected=True,all_SPEF_units_and_values_exactly_parsed=True,cell_pin_capacitance_excluded=True,
            native_macro_port_binding_complete=False,cell_and_parent_capacitance_combination_qualified=False,parent_loading_complete=False,selected=False,release_ready=False))
        save(output/'status.json',dict(state='keeper_parent_wire_RC_complete_binding_pending',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['route','layout','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['route','layout','output']))
