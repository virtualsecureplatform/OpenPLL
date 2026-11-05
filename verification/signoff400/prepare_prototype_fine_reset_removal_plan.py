"""Bind measured fine-reset removal deficits to their actual routed leaf nets."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify

def run(route,inventory,endpoints,output):
    rr=route/'assessment.json';ir=inventory/'assessment.json';design=inventory/'routed.json'
    records=[json.loads(p.read_text()) for p in (rr,ir)]
    for a in records:verify(a['artifacts'])
    m=json.loads(design.read_text())['modules']['IntegerPLL_ProgrammedCore'];cells={n.lstrip('\\'):c for n,c in m['cells'].items()}
    inputs={str(p):sha(p) for p in (rr,ir,design,route/'route.odb',Path(__file__).resolve())};targets=set()
    for directory in endpoints:
        receipt=directory/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts'])
        paths=directory/'paths.json';log=directory/'inventory.log';detail=json.loads(paths.read_text())
        for row in detail['failing_endpoint_paths']:
            if row['endpoint']=='$auto$ff.cc:337:slice$17893':continue
            if row['kind']!='min' or row['startpoint']!='$auto$ff.cc:337:slice$18697':raise ValueError('different failing endpoint class')
            checked=log.read_text().split('ALL_FAILING_ENDPOINTS_BEGIN',1)[1].split('ALL_FAILING_ENDPOINTS_END',1)[0]
            matching=[block for block in checked.split('Startpoint: ')[1:] if re.search(r'^Endpoint: '+re.escape(row['endpoint'])+r'\s*$',block,re.M) and 'Path Type: min' in block]
            if len(matching)!=1 or 'library removal time' not in matching[0]:raise ValueError('explicit removal check required')
            name=row['endpoint'];c=cells[name]
            if c['type']!='sky130_fd_sc_hs__dfstp_1' or 'SET_B' not in c['connections']:raise ValueError('expected measured set/reset storage')
            targets.add(name)
        inputs.update({str(p):sha(p) for p in (receipt,paths,log)})
    if len(targets)!=35:raise ValueError('expected exact 35 measured removal receivers')
    groups=defaultdict(list)
    for name in sorted(targets):groups[cells[name]['connections']['SET_B'][0]].append(name)
    if len(groups)!=5:raise ValueError('expected five routed leaf reset branches')
    branches=[dict(capture_cells=names,capture_master='sky130_fd_sc_hs__dfstp_1',capture_pin='SET_B',buffers=8,last_buffer_master='sky130_fd_sc_hs__clkbuf_4') for names in groups.values()]
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    save(output/'plan.json',dict(input_sha256=inputs,route_sha256=sha(route/'route.odb'),targets=[],branches=[],reset_branches=branches,reset_timing_exceptions_added=False,physical_candidate_selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','inventory','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--endpoint',type=Path,required=True,action='append')
    a=p.parse_args();run(a.route.resolve(),a.inventory.resolve(),[x.resolve() for x in a.endpoint],a.output.resolve())
