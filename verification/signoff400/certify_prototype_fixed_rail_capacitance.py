"""Exact sufficient fixed-rail C certificate via positive weighted diagonal dominance."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
import time
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from common import save,sha,verify
from resources import lease


def run(source,output):
    output.mkdir(parents=True,exist_ok=False)
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    file=source/'dynamic.pairs.jsonl';pairs=[];fixed='__fixed_rail_AC_reference';diag=defaultdict(F)
    for line in file.open():
        row=json.loads(line);a,b=row['nodes'];value=F(row['farads']);pairs.append((a,b,value))
        for n in (a,b):
            if n!=fixed:diag[n]+=value
    nodes=sorted(diag);idx={n:i for i,n in enumerate(nodes)};rows=[];cols=[];values=[]
    for a,b,value in pairs:
        if a!=fixed and b!=fixed:
            rows.extend((idx[a],idx[b]));cols.extend((idx[b],idx[a]));values.extend((-float(abs(value))*1e15,)*2)
    rows.extend(range(len(nodes)));cols.extend(range(len(nodes)));values.extend(float(diag[n])*1e15 for n in nodes)
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        comparison=coo_matrix((values,(rows,cols)),shape=(len(nodes),len(nodes))).tocsc()
        weights=spsolve(comparison,np.ones(len(nodes)))
        if not np.all(np.isfinite(weights)) or np.min(weights)<=0:raise ValueError('positive comparison weights unavailable; certificate inconclusive')
        weights/=np.max(weights);integers=np.rint(weights*10**12).astype(np.int64)
        if np.min(integers)<=0:raise ValueError('quantized weights not positive')
        w={n:int(integers[i]) for i,n in enumerate(nodes)}
        margins={n:diag[n]*w[n] for n in nodes}
        for a,b,value in pairs:
            if a!=fixed and b!=fixed:
                margins[a]-=abs(value)*w[b];margins[b]-=abs(value)*w[a]
        passed=all(v>0 for v in margins.values())
        proof=output/'weights.json';save(proof,dict(weights=w,exact_row_margins_F={n:str(v) for n,v in margins.items()}))
        pins={str(p):sha(p) for p in (receipt,file,Path(__file__).resolve())};verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(proof):sha(proof)},
            fixed_voltage_nodes=r['fixed_voltage_nodes'],dynamic_capacitor_matrix_positive_definite_certified=passed,
            method='Exact positive integer weights satisfy Cii*wi > sum_j(abs(Cij)*wj) for every free-node row; symmetric weighted strict diagonal dominance.',
            rows=len(nodes),failing_rows=sum(v<=0 for v in margins.values()),
            minimum_exact_margin_F=str(min(margins.values())),
            unrestricted_supply_port_passivity_claimed=False,intrinsic_device_capacitance_included=False,
            validated_for_prototype=False,release_ready=False))
        print('Exact fixed-rail weighted diagonal-dominance certificate:',passed,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
