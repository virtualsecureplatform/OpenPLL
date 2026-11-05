"""Bind routed FF wire loads to physical clock roots without assuming clock frequencies."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common import save,sha,verify
from compare_mapped_routed_CDC import identifier,clock_roots


def run(loads,inventory,output):
    output.mkdir(parents=True,exist_ok=False)
    lr,ir=[p/'assessment.json' for p in (loads,inventory)]
    a,b=[json.loads(p.read_text()) for p in (lr,ir)]
    lf=loads/'outputs.json';nf=inventory/'routed.json';sf=inventory/'inventory.json'
    for p,r in ((lf,a),(nf,b),(sf,b)):
        if r['artifacts'].get(str(p))!=sha(p):raise ValueError('clock/load source changed')
    root=clock_roots(json.loads(nf.read_text())['modules']['IntegerPLL_ProgrammedCore'])
    states={identifier(x['cell']):x for x in json.loads(sf.read_text())['sequential_state']}
    rows=json.loads(lf.read_text());result=[];groups=defaultdict(list);seen=set()
    for row in rows:
        name=identifier(row['routed_instance']);s=states[name]
        if name in seen or row['master']!=s['master']:raise ValueError('FF load/state identity mismatch')
        seen.add(name);domain=root(s['clock_bit']);result.append(dict(row,clock_root=list(domain)))
        groups[(tuple(domain),row['master'])].append(F(row['declared_wire_capacitance_F']))
    if seen!=set(states):raise ValueError('FF clock/load coverage incomplete')
    summary=[dict(clock_root=list(d),master=m,instances=len(v),maximum_wire_capacitance_fF=float(max(v)*10**15),
                  outputs_above_20fF_wire_alone=sum(x>F(20,10**15) for x in v)) for (d,m),v in sorted(groups.items())]
    paths=[lr,ir,lf,nf,sf,Path(__file__).resolve(),Path(__file__).with_name('compare_mapped_routed_CDC.py')]
    pins={str(p):sha(p) for p in paths};detail=output/'outputs.json';save(detail,result);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},FF_outputs=len(result),groups=summary,
         clock_polarity_retained=True,clock_frequencies_assumed=False,input_pin_and_parent_loading_included=False,
         timing_load_envelope_qualified=False,diagnostic=True,validated_for_prototype=False,release_ready=False))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('loads','inventory','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.loads.resolve(),a.inventory.resolve(),a.output.resolve())
