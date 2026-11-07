"""Bind same-route DCO wire terminals to the macro in full-parent extraction."""
import argparse,json,re,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from join_prototype_physical_instances import dimensions,join
from bind_prototype_spef_pins_v2 import bind
from resources import lease

TOP='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'

def run(extraction,rc,isolated_binding,layout,output):
    receipts=[p/'assessment.json'for p in [extraction,rc,isolated_binding,layout]];e,r,b,l=records=[json.loads(p.read_text())for p in receipts]
    for a in records:verify(a['input_sha256']);verify(a['artifacts'])
    if e['input_sha256'].get(str(receipts[-1]))!=sha(receipts[-1])or not l['all_source_macro_geometry_and_labels_preserved']:raise ValueError('same checked macro-preserving parent required')
    if not b['all_RC_terminals_bound_and_connected']or b['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):raise ValueError('same independently bound DCO route required')
    stream=Path(l['current_macro_sources_from_parent_stream']);s=json.loads(stream.read_text());verify(s['input_sha256']);verify(s['artifacts'])
    renames=s['private_cell_renames']
    if set(renames)!={'sky130_fd_sc_hs__inv_2'}:raise ValueError('one documented private keeper master required')
    reverse={v:k for k,v in renames.items()};raw=next(extraction.glob('*/capacitance.spice'));native_ext=raw.parent/(TOP+'.ext');cell='sky130_fd_sc_hd__einvp_1';cell_ext=raw.parent/(cell+'.ext');placements=isolated_binding/'placements.tsv'
    if b['artifacts'].get(str(placements))!=sha(placements):raise ValueError('placement table changed')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});lines=[];changed=0
    for line in native_ext.read_text().splitlines():
        f=line.split()
        if f[:1]==['use']and f[1]in reverse:
            old=f[1];f[1]=reverse[old];line=' '.join(f);changed+=1
        lines.append(line)
    if changed!=4:raise ValueError('four private keeper inverter uses required')
    normalized=output/'master_names_normalized.ext';normalized.write_text('\n'.join(lines)+'\n')
    grid,controls=dimensions(cell_ext.read_text(),raw.read_text(),cell);mapping,scale=join(placements.read_text(),normalized.read_text(),grid)
    jf=output/'join.json';save(jf,dict(mapping=mapping,only_master_names_normalized=renames))
    names={re.sub(r'\\(.)',r'\1',x['routed_instance']):x['extracted_instance']for x in mapping}
    folder=Path(__file__).resolve().parent;files=[*receipts,stream,raw,native_ext,cell_ext,placements,normalized,Path(__file__).resolve(),folder/'join_prototype_physical_instances.py',folder/'bind_prototype_spef_pins_v2.py'];pins={str(p):sha(p)for p in files};artifacts={str(p):sha(p)for p in [normalized,jf]};results=[];text=raw.read_text()
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for corner in ['min','nom','max']:
            parsed=rc/(corner+'.json');pins[str(parsed)]=sha(parsed)
            if r['artifacts'].get(str(parsed))!=sha(parsed):raise ValueError('DCO wire view changed')
            result=bind(json.loads(parsed.read_text()),text,TOP,names);detail=output/(corner+'.binding.json');save(detail,result);artifacts[str(detail)]=sha(detail);results.append(dict(corner=corner,networks=len(result['networks']),failures=len(result['failures']),all_RC_terminals_bound_and_connected=result['all_RC_terminals_bound_and_connected']))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,matched_instances=len(mapping),magic_grid_um=str(grid),primitive_dimension_controls=controls,all_DCO_wire_terminals_bound_inside_full_parent=all(x['all_RC_terminals_bound_and_connected']for x in results),wire_R_inserted=False,capacitance_modified=False,parent_loading_complete=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['extraction','rc','isolated-binding','layout','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n.replace('-','_')).resolve()for n in ['extraction','rc','isolated-binding','layout','output']))
