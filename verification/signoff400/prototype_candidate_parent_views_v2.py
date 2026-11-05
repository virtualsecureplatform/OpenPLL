"""Bind assembled-layout sources to the actual frame -> power -> route chain."""
import json
from pathlib import Path
from common_v3 import sha, verify
from build_assembly_frame import DCO

MASTERS={'digital':'IntegerPLL_ProgrammedCore','oscillator':DCO,'detector':'IntegerPLL_BBPD'}


def parent_views(route, power, frame):
    route,power,frame=(Path(p).resolve() for p in (route,power,frame))
    evidence={}
    def read(folder):
        path=folder/'assessment.json';evidence[str(path)]=sha(path)
        report=json.loads(path.read_text());verify(report['input_sha256']);verify(report['artifacts'])
        return report
    f,p,r=read(frame),read(power),read(route)
    def valid_bindings(report):
        if report.get('exact_macro_bindings_preserved'):return True
        proof=power/'composition.json';digest=p.get('control_buffer_composition_sha256')
        return bool(p.get('control_buffer_composition_proved') and
                    report.get('buffered_control_macro_bindings_verified') and digest and
                    p['artifacts'].get(str(proof))==digest and
                    report.get('control_buffer_composition_sha256')==digest and
                    report['input_sha256'].get(str(proof))==digest)
    sources=f.get('candidate_source_sha256')
    if not isinstance(sources,dict) or not sources:raise ValueError('explicit selected candidate source bank required')
    verify(sources)
    if p.get('candidate_source_sha256')!=sources or r.get('candidate_source_sha256')!=sources:raise ValueError('parent source identity mismatch')
    if not f.get('assembly_frame_pass') or any(f['input_sha256'].get(k)!=v for k,v in sources.items()):
        raise ValueError('assembly frame does not match current candidate')
    if not p.get('main_rail_database_connectivity_pass') or r.get('router_drc_violations')!=0 or not valid_bindings(r):
        raise ValueError('parent power/route prerequisites have not passed')
    def pinned(report,path):
        return report['input_sha256'].get(str(path))==sha(path)
    seen=set()
    def power_ancestry(folder,report):
        if folder in seen or len(seen)>=64:return False
        seen.add(folder)
        if not report.get('main_rail_database_connectivity_pass'):return False
        if pinned(report,frame/'assessment.json') and pinned(report,frame/'floorplan.odb'):
            return True
        for name in report['input_sha256']:
            path=Path(name).resolve()
            if path.name!='power.odb' or path.parent==folder:continue
            parent=path.parent
            if not pinned(report,parent/'assessment.json') or not pinned(report,path):continue
            if power_ancestry(parent,read(parent)):return True
        return False
    if not power_ancestry(power,p):
        raise ValueError('selected parent power does not descend from frame')
    visited_routes=set()
    def route_ancestry(folder,report):
        if folder in visited_routes or len(visited_routes)>=64:return False
        visited_routes.add(folder)
        if report.get('router_drc_violations')!=0 or not valid_bindings(report):return False
        if all(pinned(report,power/n) for n in ('assessment.json','power.odb')):return True
        for name in report['input_sha256']:
            path=Path(name).resolve()
            if path.name!='route.odb' or path.parent==folder:continue
            parent=path.parent
            if not pinned(report,parent/'assessment.json') or not pinned(report,path):continue
            if route_ancestry(parent,read(parent)):return True
        return False
    if not route_ancestry(route,r):raise ValueError('selected route does not descend from power')
    views=f['macro_sources']
    if set(views)!=set(MASTERS):
        raise ValueError('unexpected macro role selection')
    for role,view in views.items():
        if view['master']!=MASTERS[role]:
            raise ValueError('macro master mismatch')
        for kind in ('lef','gds'):
            path=Path(view[kind]).resolve()
            if f['input_sha256'].get(str(path))!=sha(path):
                raise ValueError('macro view not pinned by selected frame')
            evidence[str(path)]=sha(path)
    order=('digital','oscillator','detector')
    sources=[Path(views[n]['gds']).resolve() for n in order]
    return dict(candidate_source_sha256=f['candidate_source_sha256'],sources=sources,lefs=[Path(views[n]['lef']).resolve() for n in order],
                names=[views[n]['master'] for n in order],evidence_sha256=evidence,
                digital=sources[0].parents[1],dco=sources[1].parents[1],bbpd=sources[2].parents[1])
