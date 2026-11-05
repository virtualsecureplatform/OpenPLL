#!/usr/bin/env python3
"""Survey retained native split-wire R nodes against independently connected GDS.

Bind each R component to its original conductor by retained MOS/port terminals.
Use original native node seeds on their reported layer to identify independent
GDS components. Check all native R coordinates, retaining unmapped/ambiguous
seeds and failures. This does not qualify R magnitudes, junction/C placement,
virtual coordinate interpretation, supply impedance, or transient model error.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import json,math,shlex,signal,sys,time
import pya
from audit_active_dco_rc_capacitance import parse,terminals
from check_compact_clock_tree import verify
from device_aware_conductor_geometry import conductor_geometry
from check_forming_antenna_geometry_v2 import engine_at_stage
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';old=ROOT/'build/timing450/dco_c1_fine_load_001/rcx_160'
    topname='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    gds=ROOT/f'openlane/{topname}/runs/c1fine_range_001/final/gds/{topname}.gds'
    assert sha(gds)=='0f227ae41fa996eaa23410aecbe7a3b38090185285c768ba24435026f337a2dd'
    owner=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner.read_text())['deadline_uptime']
    left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME);assert left>0;signal.alarm(max(1,math.floor(left)))
    audit=base/'active_dco_rc_capacitance_audit_001/assessment.json';assert verify(audit)['actual_live_DCO_source_audited']
    raw_path=old/(topname+'.rcx.spice');original_path=base/'active_dco_lumped_capacitance_export_001/lumped_full.spice'
    ext=old/(topname+'.ext');res=old/(topname+'.res.ext')
    raw,original=parse(raw_path),parse(original_path)
    parent={}
    def find(a):
        parent.setdefault(a,a)
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    for a,b,r in raw['R']:assert r>0;parent[find(a)]=find(b)
    labels=defaultdict(set)
    for port in original['ports']:labels[find(port)].add(port)
    for name,row in original['X'].items():
        other=raw['X'][name];n=terminals(row)
        for a,b in zip(row[:n],other[:n]):labels[find(b)].add(a)
    original_nodes={n for a,b,c in original['C'] for n in [a,b]}
    for n in list(parent):
        if n in original_nodes:labels[find(n)].add(n)
    assert all(len(v)==1 for v in labels.values()),'wire R shorts distinct original conductors'
    out=base/'DCO_native_R_node_geometry_001';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=__import__('os').getpid(),original_owner=str(owner),deadline_uptime=deadline,
        total_budget_restarted=False,automatic_identical_retry=False,started_utc=datetime.now(timezone.utc).isoformat()))
    layout=pya.Layout();layout.read(str(gds));assert layout.dbu==.001
    top=layout.cell(topname);engine,regs=engine_at_stage(conductor_geometry(layout,top),'m5')
    kinds=['poly','diff','tap','li','m1','m2','m3','m4','m5']
    typemap={'p':'poly','ndif':'diff','pdif':'diff',**{f'm{i}':f'm{i}' for i in range(1,6)},'li':'li'}
    # ext linear unit 500000 is 0.005um in this retained extraction; source Tcl reports same.
    lines=[shlex.split(l) for l in ext.read_text().splitlines()]
    assert next(f for f in lines if f[0]=='scale')[3]=='500000'
    seeds={};seed_rows=[]
    offsets=[(1,1),(-1,1),(1,-1),(-1,-1),(0,0)]
    for f in lines:
        if f[0]!='node':continue
        name=f[1];kind=typemap.get(f[6]);xy=[int(f[4])*5,int(f[5])*5];found=set()
        if kind:
            for dx,dy in offsets:
                net=engine.probe_net(regs[kind],pya.Point(xy[0]+dx,xy[1]+dy))
                if net is not None:found.add(net.cluster_id)
        if len(found)==1:seeds[name]=next(iter(found))
        seed_rows.append(dict(node=name,native_type=f[6],point_nm=xy,clusters=sorted(found),unique_cluster=len(found)==1))
    cache={};records=[];stats=Counter()
    with res.open() as stream:
        for line in stream:
            if not line.startswith('rnode '):continue
            f=shlex.split(line);name=f[1];point=(int(f[4])*5,int(f[5])*5)
            names=labels[find(name)];assert len(names)<=1
            conductor=next(iter(names)) if names else None;expected=seeds.get(conductor)
            if point not in cache:
                clusters=set()
                for kind in kinds:
                    net=engine.probe_net(regs[kind],pya.Point(*point))
                    if net is not None:clusters.add(net.cluster_id)
                cache[point]=clusters
            matches=set(cache[point]);used_offset=False
            if expected is not None and expected not in matches:
                used_offset=True
                for kind in kinds:
                    for dx,dy in offsets[:-1]:
                        net=engine.probe_net(regs[kind],pya.Point(point[0]+dx,point[1]+dy))
                        if net is not None:matches.add(net.cluster_id)
            matched=expected is not None and expected in matches
            state='matched_expected_conductor' if matched else 'unresolved_original_seed' if expected is None else 'coordinate_outside_expected_conductor'
            stats[state]+=1
            records.append(dict(node=name,original_conductor=conductor,point_nm=point,expected_cluster=expected,
                physical_clusters=sorted(matches),classification=state,one_nm_boundary_neighborhood_used=used_offset))
    save(out/'original_seeds.json',seed_rows);save(out/'R_nodes.json',records)
    save(out/'unmatched.json',[r for r in records if r['classification']!='matched_expected_conductor'])
    assert records and any(r['classification']=='matched_expected_conductor' for r in records)
    # A remote coordinate has no drawn conductor, independent of logical labels.
    far=pya.Point(top.bbox().right+1000000,top.bbox().top+1000000)
    assert all(engine.probe_net(regs[k],far) is None for k in kinds)
    paths=[Path(__file__).resolve(),Path(sys.executable),gds,ext,res,raw_path,original_path,owner,audit,
        Path(__file__).with_name('audit_active_dco_rc_capacitance.py'),Path(__file__).with_name('device_aware_conductor_geometry.py'),
        Path(__file__).with_name('check_forming_antenna_geometry_v2.py')]
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='owner.json'},
        retained_native_R_nodes=len(records),original_native_nodes=len(seed_rows),unique_seed_clusters=len(seeds),
        classification_counts=dict(stats),all_R_nodes_on_expected_conductor=stats['matched_expected_conductor']==len(records),
        remote_coordinate_negative_control_rejected=True,boundary_neighborhood_nm=1,
        R_magnitudes_or_virtual_coordinate_interpretation_qualified=False,
        C_and_junction_spatial_distribution_qualified=False,transient_error_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='native_R_geometry_survey_terminal',classification_counts=dict(stats),release_qualified=False))
    print('Native DCO R geometry survey:',dict(stats),'; physical model remains unqualified.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        out=ROOT/'build/timing400/release_001/DCO_native_R_node_geometry_001'
        if out.exists():save(out/'status.json',dict(state='failed',error=repr(error),traceback=traceback.format_exc(),release_qualified=False))
        raise
