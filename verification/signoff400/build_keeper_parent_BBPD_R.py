"""Insert BBPD wire R into its parent-extracted macro while preserving all ports."""
import argparse,json,re,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from build_prototype_full_C_wire_R_v9 import build,rows
from bind_prototype_spef_pins_v2 import hierarchy
from prepare_prototype_analog_reference import subcircuits
from resources import lease
from bind_keeper_parent_BBPD_wire import TOP


def run(extraction,rc,binding,output):
    receipts=[p/'assessment.json'for p in [extraction,rc,binding]];e,r,b=records=[json.loads(p.read_text())for p in receipts]
    for a in records:verify(a['input_sha256']);verify(a['artifacts'])
    if not b['all_BBPD_wire_terminals_bound_inside_full_parent']or any(b['input_sha256'].get(str(p))!=sha(p)for p in receipts[:2]):raise ValueError('same full-parent BBPD binding required')
    raw=next(extraction.glob('*/capacitance.spice'));jf=binding/'join.json';parsed=rc/'nom.json'
    if r['artifacts'].get(str(parsed))!=sha(parsed):raise ValueError('wire view changed')
    mapping={re.sub(r'\\(.)',r'\1',x['routed_instance']):x['extracted_instance']for x in json.loads(jf.read_text())['mapping']}
    text=raw.read_text();blocks=subcircuits(text);ports=rows(blocks[TOP])[0].split()[2:];_,instances,_=hierarchy(text,raw.parent.name);selected=[x for x in instances.values()if x['model']==TOP]
    if len(selected)!=1 or selected[0]['pins'].get('SUB')!='VGND':raise ValueError('explicit extracted SUB-to-parent-VGND mapping required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});folder=Path(__file__).resolve().parent
    files=[*receipts,raw,jf,parsed,Path(__file__).resolve(),folder/'build_prototype_full_C_wire_R_v9.py',folder/'bind_keeper_parent_BBPD_wire.py'];pins={str(p):sha(p)for p in files};artifacts={};results=[]
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for attachment in ['driver','farthest']:
            model,metrics,lift=build(text,TOP,json.loads(parsed.read_text()),mapping,attachment)
            if rows(model)[0].split()[2:]!=ports:raise ValueError('parent macro interface changed')
            target=output/(attachment+'.spice');target.write_text(model);detail=output/(attachment+'.nodes.json');save(detail,dict(emitted_node_map=metrics.pop('emitted_node_map'),root_C_voltage_map=lift));artifacts.update({str(p):sha(p)for p in [target,detail]});results.append(metrics)
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,macro_interface_ports=len(ports),exact_parent_macro_port_order_preserved=True,SUB_maps_to_parent_VGND=True,parent_extracted_macro_C_retained=True,BBPD_wire_R_inserted=True,parent_composition_completed=False,spatial_C_qualified=False,passivity_qualified=False,native_simulation_allowed=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['extraction','rc','binding','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['extraction','rc','binding','output']))
