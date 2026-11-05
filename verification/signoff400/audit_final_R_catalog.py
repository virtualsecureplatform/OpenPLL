#!/usr/bin/env python3
"""Independently verify every source row in the final/superseded partition."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from common import save, sha
from resources import lease


def check_partition(source,selected,superseded,members,deadline):
    chosen={str(r['group']):r['original'] for r in members['selected_groups']}
    if len(chosen)!=members['selected_group_count']:
        raise ValueError('duplicate selected group')
    states,old_states=Counter(),Counter()
    digests=[hashlib.sha256() for _ in range(3)]
    counts=[0,0,0]
    with source.open('rb') as original,selected.open('rb') as keep,superseded.open('rb') as old:
        for raw in original:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('independent catalog audit deadline')
            digests[0].update(raw);counts[0]+=1
            r=json.loads(raw);group=r['native_group_id']
            if group in chosen:
                if r['original_conductor']!=chosen[group]:raise ValueError('selected group label mismatch')
                destination,index,table=keep,1,states
            else:
                if not 1<=int(group)<=members['obsolete_prefix_groups']:raise ValueError('unclassified source snapshot')
                destination,index,table=old,2,old_states
            actual=destination.readline()
            if actual!=raw:raise ValueError('partition row bytes differ at source row '+str(counts[0]))
            digests[index].update(actual);counts[index]+=1;table[r['catalog_state']]+=1
        if keep.read(1) or old.read(1):raise ValueError('extra partition rows')
    return counts,[h.hexdigest() for h in digests],dict(states),dict(old_states)


def run(a):
    partition,out=a.partition.resolve(),a.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(2,8,deadline):
        receipt=partition/'assessment.json';r=json.loads(receipt.read_text())
        source=Path(r['source_catalog'])/'native/tile_catalog.jsonl'
        member_path=Path(r['source_selection'])/'native_result.json'
        members=json.loads(member_path.read_text())
        if sha(member_path)!=r['input_sha256'][str(member_path)]:raise ValueError('selected membership changed')
        if members['status']!='pass' or not members['final_res_ext_node_and_resistor_multisets_match']:
            raise ValueError('unverified final export')
        selected=partition/'native/tile_catalog.jsonl';superseded=partition/'native/superseded_tile_catalog.jsonl'
        counts,hashes,states,old_states=check_partition(source,selected,superseded,members,deadline)
        if counts!=[r['source_rows'],r['selected_rows'],r['superseded_rows']]:raise ValueError('partition row count mismatch')
        if states!=r['selected_catalog_state_counts'] or old_states!=r['superseded_catalog_state_counts']:
            raise ValueError('catalog state accounting mismatch')
        expected=[r['input_sha256'][str(source)],r['artifacts'][str(selected)],r['artifacts'][str(superseded)]]
        if hashes!=expected:raise ValueError('complete source/partition digest mismatch')
        pins={str(p):sha(p) for p in (receipt,member_path,Path(__file__).resolve(),Path(__file__).with_name('common.py'),Path(__file__).with_name('resources.py'))}
        pins.update({str(p):h for p,h in zip((source,selected,superseded),hashes)})
        save(out/'assessment.json',dict(input_sha256=pins,all_source_rows_independently_partitioned=True,
            source_rows=counts[0],selected_rows=counts[1],superseded_rows=counts[2],
            selected_catalog_state_counts=states,superseded_catalog_state_counts=old_states,
            all_catalog_row_bytes_preserved=True,native_final_R_export_membership_applied=True,
            full_C_attachment_qualified=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
        print(json.dumps(dict(status='pass',source_rows=counts[0],selected_rows=counts[1],superseded_rows=counts[2])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('partition','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
