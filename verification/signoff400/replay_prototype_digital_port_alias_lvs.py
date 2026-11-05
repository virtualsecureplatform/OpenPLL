"""Restore one serializer-dropped port only after proving its raw extraction merge path."""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import shlex
import time
from common_v3 import ROOT,save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v2 import rows
from audit_prototype_macro_interface_reuse import interface
from resources import lease
from compiled_charge import execute

TOP='IntegerPLL_ProgrammedCore'
NETGEN=Path('/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen')


def restore(text,extraction,expected):
    alias,target='BBPD_RESET_N','TRACKING';blocks=subcircuits(text);block=blocks[TOP]
    header=rows(block)[0].split()[2:]
    if (len(header)!=len(set(header)) or expected-set(header)!={alias}
            or set(header)-expected or target not in header or 'R__verified_port_alias' in text):
        raise ValueError('exactly the reviewed missing output alias must differ')
    parent={};edges={};ports={};merges=0
    def find(n):
        parent.setdefault(n,n);root=n
        while parent[root]!=root:root=parent[root]
        while parent[n]!=n:
            previous=parent[n];parent[n]=root;n=previous
        return root
    for line in extraction.splitlines():
        if line.startswith('port '):
            f=shlex.split(line);ports.setdefault(f[1],set()).add(int(f[2]))
        elif line.startswith('merge '):
            f=shlex.split(line);a,b=f[1:3];merges+=1
            if find(a)!=find(b):
                parent[find(a)]=find(b)
                edges.setdefault(a,[]).append(b);edges.setdefault(b,[]).append(a)
    if set(ports)!=expected or any(len(v)!=1 for v in ports.values()):
        raise ValueError('raw port declarations differ from the actual macro interface')
    component={n for n in expected if find(n)==find(alias)}
    if component!={alias,target}:raise ValueError('raw merge graph does not prove precisely the reviewed alias')
    previous={alias:None};pending=deque([alias])
    while pending and target not in previous:
        for n in edges.get(pending.popleft(),[]):
            if n not in previous:previous[n]=True;pending.append(n)
    # Reconstruct a separate explicit witness; the tree has no cycles.
    previous={alias:None};pending=deque([alias])
    while pending and target not in previous:
        n=pending.popleft()
        for other in edges.get(n,[]):
            if other not in previous:previous[other]=n;pending.append(other)
    if target not in previous:raise ValueError('merge witness missing')
    path=[];n=target
    while n is not None:path.append(n);n=previous[n]
    path.reverse()
    lines=block.splitlines(keepends=True);end=1
    while end<len(lines) and lines[end].startswith('+'):end+=1
    if not lines[-1].lower().startswith('.ends'):raise ValueError('explicit top-level end required')
    normalized=(''.join(lines[:end])+'+ '+alias+'\n'+''.join(lines[end:-1])+
        f'R__verified_port_alias {alias} {target} 0\n'+lines[-1])
    if text.count(block)!=1:raise ValueError('unique original top block required')
    return text.replace(block,normalized,1),dict(alias=alias,target=target,
        raw_port_indices={n:next(iter(ports[n])) for n in (alias,target)},
        raw_merge_records=merges,exact_merge_witness=path,aliased_external_ports=sorted(component),
        primitive_and_other_element_cards_unchanged=True)


def run(route,output):
    source=route/'signoff';receipt=source/'assessment.json';a=json.loads(receipt.read_text());verify(a['sha256'])
    comparison=source/'compare.json';log=source/'compare.log';raw=source/(TOP+'.spice')
    ext=source/'extraction'/(TOP+'.ext');lef=route/'digital.lef';recipe=source/'compare.tcl'
    records=json.loads(comparison.read_text())
    if (a['magic_drc_rectangles'] or a['lvs_unique_match']
            or any(r.get('badnets') or r.get('badelements') for r in records)
            or records[-1]['name']!=[TOP,TOP]
            or 'Top level cell failed pin matching' not in log.read_text()):
        raise ValueError('otherwise matched digital layout with only the known port mismatch required')
    original=raw.read_text();normalized,proof=restore(original,ext.read_text(),set(interface(lef.read_text())['pins']))
    output.mkdir(parents=True,exist_ok=False);model=output/'alias_normalized.spice';model.write_text(normalized)
    detail=output/'alias_proof.json';save(detail,proof)
    text=recipe.read_text()
    if text.count(str(raw))!=1 or text.count(str(log))!=1:raise ValueError('unique original LVS source and log required')
    tcl=output/'compare.tcl';tcl.write_text(text.replace(str(raw),str(model)).replace(str(log),str(output/'compare.log')))
    setup=ROOT/'build/timing450/pdk/sky130A/libs.tech/netgen/sky130A_setup.tcl'
    files=[receipt,comparison,log,raw,ext,lef,recipe,model,detail,tcl,setup,source/'powered.v',
        source/'sky130_fd_sc_hs.canonical.spice',NETGEN,Path(__file__).resolve(),
        Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('prepare_prototype_analog_reference.py'),
        Path(__file__).with_name('build_prototype_full_C_wire_R_v2.py'),Path(__file__).with_name('audit_prototype_macro_interface_reuse.py')]
    pins={str(p):sha(p) for p in files};deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    os.chdir(output);os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with lease(1,8,deadline):execute([NETGEN,'-batch','source',tcl],output/'native.log',deadline,8)
    result=json.loads((output/'compare.json').read_text());message=(output/'compare.log').read_text()
    passed=('Circuits match uniquely.' in message and 'Top level cell failed pin matching' not in message
        and all(not r.get('badnets') and not r.get('badelements') for r in result))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()},
        digital_drc_pass=True,digital_lvs_alias_replay_pass=passed,
        raw_extraction_merge_graph_proves_port_alias=True,exact_zero_R_alias_restored=True,
        original_extraction_preserved=raw.read_text()==original,
        source_antenna_net_violations=a['antenna_net_violations'],physical_signoff_qualified=False,release_ready=False))
    print(json.dumps(dict(alias_LVS_pass=passed,witness=proof['exact_merge_witness'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.route.resolve(),a.output.resolve())
