#!/usr/bin/env python3
"""Resolve unannotated drivers and audit RESET_N extracted connectivity."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

from check_compact_mapping import LIB, TECH, LEF, OPENROAD, run
from check_compact_clock_tree import verify
from run_dco_qualification import sha, save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diode-model',required=True,type=Path)
    parser.add_argument('--route',required=True,type=Path)
    parser.add_argument('--timing',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();root=args.route.resolve();timing=args.timing.resolve();out=args.output.resolve()
    receipt=verify(root/'assessment.json');report=verify(timing/'assessment.json')
    load=args.diode_model.resolve();diode=verify(load/'assessment.json');aux=load/'antenna_diode_load.lib'
    assert receipt['conditional_diode_load_model']==str(load/'assessment.json')
    assert receipt['input_sha256'][str(aux)]==sha(aux)
    assert report['input_sha256'][str(root/'route.odb')]==sha(root/'route.odb')
    out.mkdir(parents=True,exist_ok=False)
    paths=[load/'assessment.json',aux,Path(__file__).with_name('audit_compact_parasitics.py').resolve(),Path(__file__).resolve(),Path(OPENROAD),LIB,TECH,LEF,root/'assessment.json',root/'route.odb',timing/'assessment.json']
    for rc in ('nom','min','max'):paths.extend([timing/f'400_{rc}.log',timing/f'route.{rc}.normalized.spef'])
    pins={str(p):sha(p) for p in paths}
    sets=[]
    for rc in ('nom','min','max'):
        text=(timing/f'400_{rc}.log').read_text()
        found=re.search(r'Found (\d+) unannotated drivers\.\n(.*?)Found (\d+) partially unannotated drivers',text,re.S)
        assert found and int(found[3])==0
        drivers=found[2].split();assert len(drivers)==int(found[1]);sets.append(set(drivers))
    assert sets[0]==sets[1]==sets[2]
    rows=[]
    for name in sorted(sets[0]):
        inst,pin=name.rsplit('/',1)
        assert not any(c in inst+pin for c in '{}\n')
        rows.append('{'+inst+' '+pin+'}')
    task=out/'annotation.tcl'
    task.write_text(f'''read_lef {TECH}
read_lef {LEF}
read_liberty {LIB}
read_liberty {aux}
read_db {root}/route.odb
set block [ord::get_db_block]
set output [open {out}/drivers.tsv w]
foreach pair {{{' '.join(rows)}}} {{
 lassign $pair name pin
 set inst [$block findInst $name]
 if {{$inst eq {{NULL}}}} {{error "missing annotated instance $name"}}
 set term [$inst findITerm $pin]
 if {{$term eq {{NULL}} || [$term getIoType] ne {{OUTPUT}}}} {{error "not an output $name/$pin"}}
 set net [$term getNet]
 set sinks 0
 set ports 0
 set netname NULL
 if {{$net ne {{NULL}}}} {{
  set netname [$net getName]
  foreach sink [$net getITerms] {{if {{[$sink getIoType] in {{INPUT INOUT}}}} {{incr sinks}}}}
  set ports [llength [$net getBTerms]]
 }}
 puts $output "$name/$pin\t[[$inst getMaster] getName]\t$netname\t$sinks\t$ports"
}}
close $output
exit
''')
    assert run([OPENROAD,'-exit',task],out/'annotation.log')==0
    drivers=[]
    for line in (out/'drivers.tsv').read_text().splitlines():
        name,master,net,sinks,ports=line.split('\t')
        drivers.append(dict(driver=name,master=master,net=net,sinks=int(sinks),ports=int(ports)))
    assert len(drivers)==len(sets[0])
    unused=all(d['sinks']==0 and d['ports']==0 for d in drivers)
    reset={}
    for rc in ('nom','min','max'):
        text=(timing/f'route.{rc}.normalized.spef').read_text()
        names=dict(re.findall(r'^\*(\d+) (\S+)$',text,re.M))
        identity=[i for i,n in names.items() if n=='RESET_N'];assert len(identity)==1
        block=re.search(r'^\*D_NET \*'+identity[0]+r' (.*?)^\*END',text,re.M|re.S);assert block
        body=block[1];graph=defaultdict(set)
        resistors=body.split('*RES\n',1)[1].splitlines()
        values=[]
        for line in resistors:
            if not line.strip():continue
            _,a,b,value=line.split();value=float(value);assert value>=0
            graph[a].add(b);graph[b].add(a);values.append(value)
        conn=body.split('*CONN\n',1)[1].split('*CAP',1)[0]
        endpoints=re.findall(r'^\*[IP] (\S+) [IOB]',conn,re.M)
        assert len(endpoints)>=2
        seen={endpoints[0]};pending=list(seen)
        while pending:
            node=pending.pop()
            for nxt in graph[node]-seen:seen.add(nxt);pending.append(nxt)
        reset[rc]=dict(endpoints=len(endpoints),resistors=len(values),sum_resistance_ohm=sum(values),
                       all_connection_endpoints_resistively_connected=set(endpoints)<=seen)
    for path,digest in pins.items():assert sha(Path(path))==digest,path
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        diode_load_view_conditional=True,unannotated_drivers=drivers,all_unannotated_outputs_have_no_sinks_or_ports=unused,
        reset_extracted_connectivity=reset,
        extraction_loop_warning_fidelity_qualified=False,
        physical_timing_qualified=False,release_qualified=False,
        scope='Annotation topology audit only. Connected RESET_N extraction does not prove RC loop reduction accuracy or min/max RC bounds.'))
    print(json.dumps(dict(unused_outputs_only=unused,reset=reset)),flush=True)


if __name__=='__main__':main()
