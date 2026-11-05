"""Plan same-function sizing and bounded fanout splits from measured slew failures."""
import argparse
import json
from pathlib import Path
import re
from common_v3 import save,sha,verify

def run(previews,inventory,route,output):
    receipt=inventory/'assessment.json'; inv=json.loads(receipt.read_text());verify(inv['artifacts'])
    routed=inventory/'routed.json'; m=json.loads(routed.read_text())['modules']['IntegerPLL_ProgrammedCore'];cells={n.lstrip('\\'):c for n,c in m['cells'].items()}
    pins={str(x):sha(x) for x in (receipt,routed,route/'route.odb',Path(__file__).resolve())}; changes={}; bits=set()
    for directory in previews:
        p=directory/'assessment.json';a=json.loads(p.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if a['input_sha256'].get(str(routed))!=sha(routed):raise ValueError('different route inventory')
        last=a['history'][-1]['iteration'];script=directory/f'preview_{last}.tcl';log=directory/f'preview_{last}.log'
        # Derive only changes actually tested in the final frozen-wire preview.
        for name,new in re.findall(r'^replace_cell \{([^}]+)\} (\S+)$',script.read_text(),re.M):
            old=cells[name]['type']
            if old.rsplit('_',1)[0]!=new.rsplit('_',1)[0]:raise ValueError('non-equivalent cell family')
            if name not in changes or int(changes[name]['replacement_master'].rsplit('_',1)[1])<int(new.rsplit('_',1)[1]):
                changes[name]=dict(action='resize',capture_cell=name,capture_master=old,replacement_master=new)
        for pin in re.findall(r'^(\S+)\s+[\d.]+\s+[\d.]+\s+[-\d.]+ \(VIOLATED\)',log.read_text(),re.M):
            name,port=pin.rsplit('/',1);bits.update(cells[name]['connections'][port])
        pins.update({str(x):sha(x) for x in (p,script,log)})
    branches=[]
    for bit in sorted(bits):
        drivers=[];sinks=[]
        for n,c in cells.items():
            for port,bs in c['connections'].items():
                if bs!=[bit]:continue
                if c['port_directions'].get(port)=='output':drivers.append(dict(cell=n,pin=port,master=changes.get(n,{}).get('replacement_master',c['type'])))
                elif c['port_directions'].get(port)=='input':sinks.append(dict(cell=n,pin=port,master=changes.get(n,{}).get('replacement_master',c['type'])))
        if len(drivers)!=1 or not sinks:raise ValueError('unique driven scalar net required')
        branches.append(dict(driver=drivers[0],sinks=sinks,max_sinks_per_buffer=8,buffer_master='sky130_fd_sc_hs__clkbuf_2'))
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    save(output/'plan.json',dict(input_sha256=pins,route_sha256=sha(route/'route.odb'),targets=list(changes.values()),branches=branches,physical_candidate_selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--preview',type=Path,action='append',required=True)
    for n in ('inventory','route','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run([x.resolve() for x in a.preview],a.inventory.resolve(),a.route.resolve(),a.output.resolve())
