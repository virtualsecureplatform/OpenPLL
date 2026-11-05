"""Locate every negative retained SPICE C token in the existing native R basis."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import time
from common import save,sha
from resources import lease


def value(token):
    scales={'f':Decimal('1e-15'),'p':Decimal('1e-12'),'n':Decimal('1e-9'),'u':Decimal('1e-6'),'m':Decimal('1e-3'),'k':Decimal('1e3'),'G':Decimal('1e9')}
    result=Decimal(token[:-1])*scales[token[-1]] if token[-1] in scales else Decimal(token)
    if not result.is_finite():raise ValueError('nonfinite C token')
    return result


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    deck=Path('/tmp/openpll-interface-domain-_9_bmlz2/domain/trace/retained_rc.spice')
    nodes=Path('/tmp/openpll-native-R-core-nh81fygy/native_core_nodes.jsonl')
    base=Path('build/signoff400').resolve()
    inventory=base/'startup_timing_SPICE_cap_token_inventory_003/assessment.json'
    core=base/'startup_timing_final_native_R_core_002/assessment.json'
    paths=[deck,nodes,inventory,core,Path(__file__).resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(2,4,deadline):
        pins={str(p):sha(p) for p in paths}
        inv,c=[json.loads(p.read_text()) for p in (inventory,core)]
        if inv['input_sha256'][str(deck)]!=pins[str(deck)] or c['artifacts'][str(nodes)]!=pins[str(nodes)]:raise ValueError('native input lineage mismatch')
        caps=[];wanted=set();negative_sum=Decimal(0);total=0
        with deck.open() as stream:
            for number,line in enumerate(stream,1):
                if number%1000000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('deck audit deadline')
                if not line.startswith('C'):continue
                fields=line.split();total+=1
                if not fields[3].startswith('-'):continue
                cap=value(fields[3])
                if cap>=0:continue
                caps.append(dict(line_number=number,instance=fields[0],endpoints=fields[1:3],SPICE_token=fields[3],SI_F=str(cap),raw_EXT_units=str(cap*Decimal('1e18'))))
                wanted.update(fields[1:3]);negative_sum+=cap
        if total!=inv['results']['capacitor_records'] or len(caps)!=inv['results']['negative_capacitor_records']:raise ValueError('independent C count mismatch')
        binding={}
        with nodes.open() as stream:
            for line in stream:
                row=json.loads(line)
                if row['printed_name'] in wanted:
                    if row['printed_name'] in binding:raise ValueError('ambiguous native R name')
                    binding[row['printed_name']]=row
        if set(binding)!=wanted:raise ValueError('negative C endpoint absent from native R basis')
        pairs=Counter();same=0;conductor_set=set()
        target=output/'negative_capacitor_bindings.jsonl'
        with target.open('x') as stream:
            for row in caps:
                row['native_R_endpoints']=[binding[n] for n in row['endpoints']]
                conductors=tuple(r['original_conductor'] for r in row['native_R_endpoints'])
                pairs[conductors[1]]+=1;conductor_set.update(conductors);same+=conductors[0]==conductors[1]
                stream.write(json.dumps(row)+'\n')
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('source changed during audit')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target)},
            every_negative_SPICE_capacitor_bound_to_exact_native_R_nodes=True,
            independently_scanned_capacitor_records=total,negative_capacitor_records=len(caps),
            negative_capacitance_sum_SI_F=str(negative_sum),
            second_endpoint_original_conductor_counts=dict(pairs),distinct_original_conductors=len(conductor_set),
            same_original_conductor_negative_edges=same,
            negative_values_are_preserved=True,negative_values_removed=False,
            full_matrix_passivity_verified=False,full_SPICE_matrix_equivalence_verified=False,
            physical_RC_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
