#!/usr/bin/env python3
"""Bind native R-node provenance to retained output and inspect unresolved supports.

Require unchanged native output controls first. Select the last complete output
for each original conductor (the explicit all-net pass supersedes the automatic
subset). Check every emitted node name/coordinate against .res.ext, then retain
node origin bits and incident material names for unresolved/body coordinates.
Material labels alone are not independent physical support or impedance proof.
"""
from collections import Counter,defaultdict
from pathlib import Path
import json,shlex
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def read_trace(path):
    types={};groups={};current=None;order=[]
    with path.open() as stream:
        for line in stream:
            f=shlex.split(line);assert f
            if f[0]=='TYPE':
                assert current is None and len(f)==3 and f[1] not in types;types[f[1]]=f[2]
            elif f[0]=='BEGIN':
                assert current is None and len(f)==3 and f[1] not in groups
                current=dict(id=f[1],original=f[2],nodes={},edges=[]);order.append(f[1])
            elif f[0]=='NODE':
                assert current is not None and len(f)==8 and f[1]==current['id'] and f[2] not in current['nodes']
                current['nodes'][f[2]]=dict(name=f[3],point_internal=list(map(int,f[4:6])),why=int(f[6]),status=int(f[7]))
            elif f[0]=='EDGE':
                assert current is not None and len(f)==8 and f[1]==current['id']
                assert f[6] in types,f
                current['edges'].append(dict(owner=f[2],a=f[3],b=f[4],milliohm=f[5],type_id=f[6],status=int(f[7])))
            elif f[0]=='END':
                assert current is not None and len(f)==2 and f[1]==current['id']
                assert all(r['owner'] in current['nodes'] and r['a'] in current['nodes'] and r['b'] in current['nodes'] for r in current['edges'])
                groups[current['id']]=current;current=None
            else:raise AssertionError(f)
    assert current is None and groups and types
    return types,[groups[x] for x in order]


def main():
    base=ROOT/'build/timing400/release_001';receipt=base/'DCO_R_node_trace_controls_001/assessment.json'
    assert verify(receipt)['installed_default_and_R_trace_native_intermediate_records_identical']
    source=receipt.parent/'trace';log=source/'R_provenance.log'
    types,groups=read_trace(log);last={g['original']:g for g in groups}
    rows=[];counter=Counter()
    for group in last.values():
        incident=defaultdict(list)
        for edge in group['edges']:incident[edge['owner']].append(edge)
        for ptr,row in group['nodes'].items():
            materials=Counter(types[e['type_id']] for e in incident[ptr])
            xy=row['point_internal'];counter[row['name'],*xy]+=1
            rows.append(dict(original_conductor=group['original'],**row,
                point_nm=[x*5 for x in xy],incident_material_counts=dict(materials),
                origin_flags=[name for bit,name in [(1,'junction'),(2,'device'),(4,'contact'),(8,'origin'),(16,'sink')] if row['why']&bit]))
    top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    native=Counter()
    for line in (source/(top+'.res.ext')).open():
        if line.startswith('rnode '):
            f=shlex.split(line);native[f[1],int(f[4]),int(f[5])]+=1
    assert counter==native,(sum(counter.values()),sum(native.values()),list((counter-native).items())[:3])
    prior=base/'DCO_native_R_node_geometry_002';unmatched=json.loads((prior/'unmatched.json').read_text())
    selected={(r['node'],*r['point_nm']):r for r in unmatched if r['classification'] in ['coordinate_outside_expected_conductor','native_MOS_body_terminal_not_covered_by_wire_only_geometry']}
    details=[]
    for row in rows:
        k=(row['name'],*row['point_nm'])
        if k in selected:details.append(dict(**row,prior_classification=selected[k]['classification']))
    ground=[r for r in details if r['prior_classification']=='coordinate_outside_expected_conductor']
    assert len(ground)==34
    out=base/'DCO_R_node_provenance_inspection_001';out.mkdir(exist_ok=False)
    save(out/'node_metadata.json',rows);save(out/'unresolved_and_body_metadata.json',details);save(out/'ground_internal_metadata.json',ground)
    summary=dict(groups_in_native_log=len(groups),last_all_net_groups=len(last),native_node_coordinate_records=sum(counter.values()),
        native_node_coordinate_multiset_exactly_recovered=True,
        ground34_origin_flags=dict(Counter(tuple(r['origin_flags']) for r in ground)),
        ground34_material_names=sorted({name for r in ground for name in r['incident_material_counts']}))
    # JSON object keys for flag combinations must be plain strings.
    summary['ground34_origin_flags']={','.join(k):v for k,v in summary['ground34_origin_flags'].items()}
    save(out/'summary.json',summary)
    paths=[Path(__file__).resolve(),receipt,log,source/(top+'.res.ext'),prior/'assessment.json',prior/'unmatched.json']
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={str(p):sha(p) for p in out.iterdir()},
        **summary,independent_bulk_geometry_or_impedance_qualified=False,C_or_junction_distribution_qualified=False,
        transient_error_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Native R provenance inspection:',summary)


if __name__=='__main__':main()
