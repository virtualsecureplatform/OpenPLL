"""Audit terminal isolated keeper routes before allowing analog extraction."""
import argparse,json,re
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity


def run(source,output):
    import klayout.db as k
    owner=json.loads((source/'owner.json').read_text())
    if identity(owner['pid'])==owner['birth']:raise ValueError('route owner still live; preserve original job')
    status=json.loads((source/'status.json').read_text())
    if status['state']not in ['stopped_without_promotion','keeper_macro_route_complete_qualification_pending']:
        raise ValueError('route is not terminal')
    manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    cfgpath=source/'config/config.json';cfg=json.loads(cfgpath.read_text())
    flow=source/'config/runs/history_keeper_macros_001';metrics_path=flow/'final/metrics.json'
    metrics=json.loads(metrics_path.read_text());paths=[manifest,source/'status.json',cfgpath,metrics_path,Path(__file__).resolve()]
    required=['design__power_grid_violation__count','route__drc_errors','magic__drc_error__count',
        'klayout__drc_error__count','design__lvs_error__count','antenna__violating__nets',
        'route__antenna_violation__count']
    checks={key:dict(observed=metrics.get(key),pass_check=key in metrics and metrics[key]==0)for key in required}
    lvs=next(flow.glob('*netgen-lvs/reports/lvs.netgen.rpt'));j=lvs.with_suffix('.json');paths.extend([lvs,j])
    report=lvs.read_text();records=json.loads(j.read_text());top=cfg['DESIGN_NAME']
    unique='Final result: Circuits match uniquely.'in report and 'Property errors were found'not in report and 'Top level cell failed pin matching'not in report
    complete=records[-1].get('name')==[top,top] and all(not r.get('badnets')and not r.get('badelements')and not r.get('properties')for r in records)
    checks['native_LVS']=dict(unique_match=unique,all_records_without_discrepancies=complete,pass_check=unique and complete)
    gds=flow/'final/gds'/(top+'.gds');paths.append(gds);layout=k.Layout();layout.read(str(gds));macro_checks=[]
    for name,macro in cfg['MACROS'].items():
        if len(macro['gds'])!=1:raise ValueError('expected one macro GDS view')
        original=Path(macro['gds'][0]);paths.append(original);lib=k.Layout();lib.read(str(original))
        actual=layout.cell(name);expected=lib.cell(name);differences=[]
        if actual is not None and expected is not None and layout.dbu==lib.dbu:
            for info in set(layout.layer_infos()+lib.layer_infos()):
                a=k.Region(actual.begin_shapes_rec(layout.layer(info)));b=k.Region(expected.begin_shapes_rec(lib.layer(info)))
                if (a^b).area():differences.append(str(info))
        else:differences=['missing cell or DBU mismatch']
        count=sum(1 for i in layout.cell(top).each_inst()if i.cell.name==name)
        nonempty=actual is not None and not actual.is_empty()
        macro_checks.append(dict(name=name,source_geometry_matches=not differences,different_layers=differences,
            nonempty=nonempty,instances=count,expected_instances=len(macro['instances']),
            pass_check=not differences and nonempty and count==len(macro['instances'])))
    checks['macro_geometry']=dict(cells=macro_checks,pass_check=bool(macro_checks)and all(x['pass_check']for x in macro_checks))
    verify(m['input_sha256']);pins={str(p):sha(p)for p in paths}
    output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256=pins,source_input_sha256=m['input_sha256'],checks=checks,
        candidate_physical_checks_pass=all(x['pass_check']for x in checks.values()),
        extraction_allowed=all(x['pass_check']for x in checks.values()),
        timing_corners_qualified=False,full_parent_qualified=False,analog_qualified=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.source.resolve(),a.output.resolve())
