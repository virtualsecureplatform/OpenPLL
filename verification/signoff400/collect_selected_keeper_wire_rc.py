"""Collect completed keeper RCX views without rerunning extraction."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from prototype_spef_v2 import parse


def run(route,audit,output):
    a=json.loads(audit.read_text());verify(a['input_sha256']);verify(a['source_input_sha256'])
    if not a['candidate_physical_checks_pass']:raise ValueError('physical candidate audit must pass')
    output.mkdir(parents=True,exist_ok=False)
    flow=route/'config/runs/history_keeper_macros_001';rcx=flow/'47-openroad-rcx'
    state=rcx/'state_in.json';s=json.loads(state.read_text());cfg=rcx/'config.json'
    gds=flow/'final/gds'
    gdsfiles=list(gds.glob('*.gds'))
    if len(gdsfiles)!=1 or a['input_sha256'].get(str(gdsfiles[0]))!=sha(gdsfiles[0]):raise ValueError('RCX route differs from audited GDS')
    paths=[Path(__file__).resolve(),Path(__file__).with_name('prototype_spef_v2.py'),audit,state,cfg,Path(s['odb']),gdsfiles[0]]
    results=[];artifacts={}
    for corner in ['nom','min','max']:
        files=list((rcx/corner).glob('*.spef'))
        if len(files)!=1:raise ValueError('one SPEF per RC corner required')
        spef=files[0];log=rcx/corner/'rcx.log';paths.extend([spef,log])
        parsed=parse(spef.read_text())
        if parsed['design']!=gdsfiles[0].stem or not parsed['pin_capacitance_excluded']:raise ValueError('SPEF design or capacitance scope mismatch')
        target=output/(corner+'.json');save(target,parsed);artifacts[str(target)]=sha(target)
        results.append(dict(corner=corner,nets=len(parsed['nets']),connections=sum(len(n['connections'])for n in parsed['nets']),
            resistors=sum(len(n['resistors'])for n in parsed['nets']),capacitors=sum(len(n['capacitors'])for n in parsed['nets']),
            zero_resistors=sum(r['ohms']=='0'for n in parsed['nets']for r in n['resistors']),pin_capacitance_excluded=True))
    pins={str(p):sha(p)for p in paths};verify(a['input_sha256'])
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
        completed_same_route_RCX_views_collected=True,exact_SPEF_units_and_values_parsed=True,
        RC_pin_binding_complete=False,capacitance_combination_validated=False,
        cell_internal_resistance_included=False,parent_loading_complete=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--route',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.route.resolve(),a.audit.resolve(),a.output.resolve())
