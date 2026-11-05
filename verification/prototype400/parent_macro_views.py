"""Bind assembled-layout sources to the actual frame -> power -> route chain."""
import json
from pathlib import Path
from common import source_pins, sha, verify
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
    if not f.get('assembly_frame_pass') or any(f['input_sha256'].get(k)!=v for k,v in source_pins().items()):
        raise ValueError('assembly frame does not match current candidate')
    if not p.get('main_rail_database_connectivity_pass') or r.get('router_drc_violations')!=0 or not r.get('exact_macro_bindings_preserved'):
        raise ValueError('parent power/route prerequisites have not passed')
    for report,parent,artifact in ((p,frame,'floorplan.odb'),(r,power,'power.odb')):
        for name in ('assessment.json',artifact):
            path=parent/name
            if report['input_sha256'].get(str(path))!=sha(path):
                raise ValueError('selected parent CAD ancestry mismatch')
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
    return dict(sources=sources,lefs=[Path(views[n]['lef']).resolve() for n in order],
                names=[views[n]['master'] for n in order],evidence_sha256=evidence,
                digital=sources[0].parents[1],dco=sources[1].parents[1],bbpd=sources[2].parents[1])
