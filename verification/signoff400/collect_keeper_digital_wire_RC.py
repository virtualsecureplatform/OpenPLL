"""Extract digital wire views from the exact checked macro route in current parent."""
import argparse,json,re,os,time,shutil
from fractions import Fraction as F
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from prototype_spef_v2 import parse
from extract_prototype_parent_spef_v2 import check_network,OPENROAD
from resources import lease,identity
from compiled_charge_v2 import execute


def run(route,layout,output):
    rr=route/'assessment.json';sr=route/'signoff/assessment.json';lr=layout/'assessment.json';r,s,l=[json.loads(p.read_text())for p in [rr,sr,lr]]
    for a in [r,l]:verify(a['input_sha256']);verify(a['artifacts'])
    verify(s['sha256'])
    stream=Path(l['current_macro_sources_from_parent_stream']);a=json.loads(stream.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    db=route/'route.odb';gds=route/'signoff/route.gds'
    if not l['assembled_drc_pass']or not l['assembled_lvs_pass']or not l['all_source_macro_geometry_and_labels_preserved']:raise ValueError('checked macro-preserving parent required')
    if s['magic_drc_rectangles']!=0 or not s['lvs_unique_match']or r['router_drc_violations']!=0:raise ValueError('checked digital route required')
    if s['sha256'].get(str(db))!=sha(db)or s['sha256'].get(str(gds))!=sha(gds)or a['input_sha256'].get(str(gds))!=sha(gds):raise ValueError('digital database/GDS differs from current parent source')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600;os.sched_setaffinity(0,{24,25});os.environ.update(OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=2,memory_GiB=8))
    folder=Path(__file__).resolve().parent;pins={str(p):sha(p)for p in [rr,sr,lr,stream,db,gds,OPENROAD,Path(__file__).resolve(),folder/'prototype_spef_v2.py',folder/'extract_prototype_parent_spef_v2.py']};artifacts={};results=[];wires=output/'signal_wires.tsv';unwired=output/'unwired_single_terminal.tsv';rules=ROOT/'build/timing450/pdk/sky130A/libs.tech/librelane'
    try:
        for corner in ['min','nom','max']:
            model=rules/f'rules.openrcx.sky130A.{corner}.magic';pins[str(model)]=sha(model);script=output/(corner+'.tcl');target=output/(corner+'.spef')
            query='set f [open {'+str(wires)+'} w]\nset u [open {'+str(unwired)+'} w]\nforeach net [[ord::get_db_block] getNets] {\n if {[$net getSigType] ni {POWER GROUND}} {\n  if {[$net getWire] == "NULL"} {\n   set ni [llength [$net getITerms]]\n   set nb [llength [$net getBTerms]]\n   if {$ni+$nb > 1} {error "multi-terminal signal missing detailed wire"}\n   puts $u [join [list [$net getName] $ni $nb] "\\t"]\n   continue\n  }\n  puts $f [$net getName]\n }\n}\nclose $f\nclose $u\n'
            script.write_text(f'read_db {{{db}}}\nset_thread_count 2\n'+query+f'define_process_corner -ext_model_index 0 RCX_{corner.upper()}\nextract_parasitics -ext_model_file {{{model}}} -corner 0\nwrite_spef {{{target}}}\nexit\n');pins[str(script)]=sha(script);verify(pins)
            save(output/'status.json',dict(state='extracting_digital_'+corner,release_ready=False))
            if corner=='nom':
                original=route/'route.nom.spef';pins[str(original)]=sha(original)
                if not r['nominal_rc_extracted']or r['artifacts'].get(str(original))!=sha(original)or r['input_sha256'].get(str(model))!=sha(model):raise ValueError('same completed nominal extraction required')
                shutil.copy2(original,target);reuse=output/'nom.reuse.json';save(reuse,dict(source=str(original),source_receipt=str(rr),source_sha256=sha(original),native_extraction_rerun=False));artifacts[str(reuse)]=sha(reuse)
            else:
                with lease(2,8,deadline):execute([OPENROAD,'-no_init','-exit',script],output/(corner+'.log'),deadline,8)
            parsed=parse(target.read_text());expected={re.sub(r'\\(.)',r'\1',n)for n in wires.read_text().splitlines()};found={re.sub(r'\\(.)',r'\1',n['name'])for n in parsed['nets']}
            if not expected or expected!=found or not parsed['pin_capacitance_excluded']:raise ValueError('wire inventory or PIN_CAP scope differs')
            networks=[check_network(n)for n in parsed['nets']]
            if any(F(x['ohms'])<=0 for n in parsed['nets']for x in n['resistors']):raise ValueError('strictly positive wire R required')
            detail=output/(corner+'.json');save(detail,parsed);artifacts.update({str(p):sha(p)for p in [target,detail,*([output/(corner+'.log')]if corner!='nom'else[])]});results.append(dict(corner=corner,reused_completed_native_extraction=corner=='nom',nets=len(networks),terminals=sum(x['terminals']for x in networks),resistors=sum(x['resistors']for x in networks)))
        artifacts[str(wires)]=sha(wires);artifacts[str(unwired)]=sha(unwired);verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,exact_digital_source_used_in_parent=True,cell_pin_capacitance_excluded=True,terminals_resistively_connected=True,unwired_single_terminal_nets_recorded=True,unwired_multi_terminal_nets_rejected=True,wire_binding_complete=False,native_simulation_allowed=False,release_ready=False));save(output/'status.json',dict(state='digital_wire_RC_complete_binding_pending',release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['route','layout','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['route','layout','output']))
