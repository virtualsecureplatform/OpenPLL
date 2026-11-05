"""Independently replay exact diagonal certificates and report necessary PSD witnesses."""
import argparse
import json
import os
from pathlib import Path
import time
from common import save, sha, verify
from resources import identity, lease


def audit_rows(path, nodes, deadline):
    count=negative=zero=0;minimum=0;witnesses=[]
    with path.open() as stream:
        for line in stream:
            if count%10000==0 and time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                raise TimeoutError('exact row replay deadline')
            row=json.loads(line)
            if type(row['row']) is not int or row['row']!=count or count>=nodes:
                raise ValueError('exact certificate row coverage/order')
            d,r,l1,c,new=(int(row[k]) for k in ('stored_diagonal_integer','residual_integer',
                         'L1_integer','diagonal_correction_integer','conservative_diagonal_integer'))
            if c!=-r or new!=d+c or l1<abs(r) or l1<abs(d):
                raise ValueError('inconsistent exact conservative diagonal certificate')
            if new<0:
                negative+=1;minimum=min(minimum,new)
                if len(witnesses)<32:witnesses.append(dict(row=count,energy_integer=str(new),
                    voltage_definition='one on this voltage node, zero on every other voltage node'))
            zero+=new==0;count+=1
    if count!=nodes:raise ValueError('incomplete exact row certificate')
    return dict(rows=count,negative_conservative_diagonals=negative,zero_conservative_diagonals=zero,
                minimum_conservative_diagonal_integer=str(minimum),negative_energy_witnesses=witnesses,
                full_matrix_passivity_verified=False,physical_RC_qualified=False,release_qualified=False)


def run(source,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=1,memory_GiB=1,automatic_identical_retry=False))
    try:
        assessment=source/'assessment.json';a=json.loads(assessment.read_text())
        if not a['conservative_C_stored_coefficient_derivative_certified']:
            raise ValueError('complete conservative coefficient certificate required')
        operator=Path(a['logical_operator_manifest']);manifest=json.loads(operator.read_text())
        rows=Path(manifest['correction_certificate']['path'])
        if sha(operator)!=a['artifacts'][str(operator)] or manifest['correction_certificate']['sha256']!=a['artifacts'][str(rows)]:
            raise ValueError('operator/certificate identity mismatch')
        paths=[assessment,operator,rows,Path(__file__).resolve()]
        with lease(1,1,deadline):
            pins={str(p):sha(p) for p in paths}
            if pins[str(rows)]!=a['artifacts'][str(rows)]:raise ValueError('row certificate changed')
            save(output/'status.json',dict(state='replaying_every_exact_conservative_row',release_qualified=False))
            result=audit_rows(rows,manifest['node_count'],deadline)
            result['energy_binary_quantum_exponent']=manifest['correction_certificate']['binary_quantum_exponent']
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={},results=result,
                 exact_row_certificate_independently_replayed=True,full_matrix_passivity_verified=False,
                 physical_RC_qualified=False,release_qualified=False))
            save(output/'status.json',dict(state='exact_row_replay_complete',release_qualified=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(error),release_qualified=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();run(args.source.resolve(),args.output.resolve())
