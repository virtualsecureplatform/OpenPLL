#!/usr/bin/env python3
"""Trace gate-to-port connectivity with higher metal layers absent.

Tests whether an external diode could reach a reported gate at the failing
formation layer. This is a necessary topology condition, not antenna sizing
or electrical qualification. Full-stack matches and wrong-port controls are
required before interpreting the earlier-stage results.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import signal
import sys

import pya

from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('12h formation audit')))
    signal.alarm(43200)
    base=ROOT/'build/timing400/release_001'
    localized=base/'candidate_antenna_localization_003'
    verify(localized/'assessment.json')
    records=json.loads((localized/'debug_records.json').read_text())
    assert len(records)==151 and all(r['exact_gate_match'] for r in records)
    stream=verify(base/'candidate_stream_filled_002/assessment.json')
    assert stream['all_source_macro_geometry_and_labels_preserved']
    dco='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    macros={
        'IntegerPLL_AcquiringCore':(base/'compact_incremental_headroom_001/signoff/route.gds',(150000,150000)),
        dco:(ROOT/f'openlane/{dco}/runs/c1fine_range_001/final/gds/{dco}.gds',(750000,150000)),
        'IntegerPLL_BBPD':(ROOT/'build/timing450/interface_characterization/bbpd_sampled/runs/timing450_sampled_v2/final/mag_gds/IntegerPLL_BBPD.magic.gds',(750000,400000))}
    files=[Path(__file__).resolve(),Path(sys.executable),localized/'assessment.json',localized/'debug_records.json',base/'candidate_stream_filled_002/assessment.json']
    groups=defaultdict(list)
    skipped=[]
    for index,row in enumerate(records):
        x0,y0,x1,y1=(v*5 for v in row['gate_box_internal_units'])
        owner=[name for name,(_,offset) in macros.items()
            if any(a.startswith(name+'_0/') for a in row['named_port_aliases'])
            and offset[0]<=x0<x1<=offset[0]+(455000 if name=='IntegerPLL_AcquiringCore' else 125000)
            and offset[1]<=y0<y1<=offset[1]+(455000 if name=='IntegerPLL_AcquiringCore' else 125000)]
        if not owner:
            assert not row['named_port_aliases']
            skipped.append(index);continue
        assert len(owner)==1
        name=owner[0];ports=[a.split('/',1)[1] for a in row['named_port_aliases'] if a.startswith(name+'_0/')]
        assert len(ports)==1,(name,ports)
        groups[name].append(dict(record=index,port=ports[0],root=row['extracted_net_roots'][0],
            stage=int(re.search(r'metal(\d+)',row['plane'])[1]),
            gate_point=(int((x0+x1)/2-macros[name][1][0]),int((y0+y1)/2-macros[name][1][1]))))
    results=[];negative=0
    for name,rows in groups.items():
        path,offset=macros[name];files.append(path)
        ext=base/f'candidate_antenna_002/extraction/{name}.ext';files.append(ext)
        ports=defaultdict(list)
        for port,x0,y0,x1,y1,layer in re.findall(r'^port "([^"]+)" \d+ (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)$',ext.read_text(),re.M):
            if layer.startswith('m') and layer[1:].isdigit():
                ports[port].append((int(layer[1:]),pya.Point((int(x0)+int(x1))*5//2,(int(y0)+int(y1))*5//2)))
        layout=pya.Layout();layout.read(str(path));assert layout.dbu==0.001
        top=layout.cell(name);assert top is not None

        def layer(number,datatype):
            return pya.Region(top.begin_shapes_rec(layout.layer(number,datatype))).merged()

        geometry={'poly':layer(66,20),'tap':layer(65,44),'licon':layer(66,44),'li':layer(67,20),'mcon':layer(67,44)}
        geometry['diff']=layer(65,20)-geometry['poly']
        for level in range(1,6):geometry[f'm{level}']=layer(67+level,20)
        for level in range(1,5):geometry[f'v{level}']=layer(67+level,44)
        stages=sorted({r['stage'] for r in rows}|{5})
        bystage={}
        for stage in stages:
            engine=pya.LayoutToNetlist('FLAT',0.001)
            selected=['poly','diff','tap','licon','li','mcon']+[f'm{i}' for i in range(1,stage+1)]+[f'v{i}' for i in range(1,stage)]
            regs={key:pya.Region(geometry[key]) for key in selected}
            for key,value in regs.items():engine.register(value,key);engine.connect(value)
            for key in ('poly','diff','tap','li'):engine.connect(regs[key],regs['licon'])
            engine.connect(regs['li'],regs['mcon']);engine.connect(regs['mcon'],regs['m1'])
            for i in range(1,stage):
                engine.connect(regs[f'm{i}'],regs[f'v{i}']);engine.connect(regs[f'v{i}'],regs[f'm{i+1}'])
            engine.extract_netlist()

            def probe(key,point):
                net=engine.probe_net(regs[key],point)
                return None if net is None else net.cluster_id

            def probe_port(port):
                return {cluster for level,point in ports[port] if level<=stage
                    for cluster in [probe(f'm{level}',point)] if cluster is not None}

            observed=[]
            for row in rows:
                gate=probe('poly',pya.Point(*row['gate_point']));assert gate is not None,(name,row)
                pids=probe_port(row['port'])
                observed.append(dict(record=row['record'],macro=name,port=row['port'],stage=stage,
                    gate_to_port_connected=gate in pids,port_present_at_stage=bool(pids),
                    native_failure_stage=row['stage']))
                if stage==5:
                    assert gate in pids,('full stack fails native net binding',name,row)
                    wrong=next(other for other in rows if other['root']!=row['root'])
                    assert gate not in probe_port(wrong['port']),('wrong port short',name,row,wrong)
                    negative+=1
            bystage[stage]=observed
        for row in rows:
            observed=next(r for r in bystage[row['stage']] if r['record']==row['record'])
            results.append(observed)
        print(json.dumps(dict(macro=name,records=len(rows),external_port_reachable_at_failure=sum(r['gate_to_port_connected'] for r in results if r['macro']==name))),flush=True)
    assert negative==150 and len(results)==150 and len(skipped)==1
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    save(out/'formation_records.json',results)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        fully_formed_native_gate_port_bindings_passed=150,wrong_port_controls_rejected=negative,
        internal_only_violation_records=skipped,
        external_port_reachable_at_failure_records=sum(r['gate_to_port_connected'] for r in results),
        all_port_records=len(results),antenna_qualified=False,release_qualified=False,adopted=False,scope=__doc__))


if __name__=='__main__':
    main()
