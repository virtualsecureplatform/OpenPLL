#!/usr/bin/env python3
"""Apply proven native final-export membership to an audited tile catalog."""
import argparse
import json
from pathlib import Path
import time
from common import ROOT, save, sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease


def run(a):
    catalog,audit,selection,binary,out=(p.resolve() for p in
        (a.catalog,a.audit,a.selection,a.binary,a.output))
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(out/'status.json',dict(state='verifying_final_export_and_catalog_lineage',release_qualified=False))
    with lease(2,8,deadline):
        cr,ar,sr=[p/'assessment.json' for p in (catalog,audit,selection)]
        c,v,s=[json.loads(p.read_text()) for p in (cr,ar,sr)]
        source=catalog/'native/tile_catalog.jsonl';members=selection/'native_result.json'
        if not v['all_native_tile_rows_independently_checked'] or v['input_sha256'].get(str(cr))!=sha(cr):
            raise ValueError('matching complete independent catalog audit required')
        if not s['native_final_R_export_snapshot_mapping_verified'] or not s['final_res_ext_node_and_resistor_multisets_match']:
            raise ValueError('verified final native snapshot mapping required')
        domains=[p for p in c['input_sha256'] if p.endswith('/domain/assessment.json')]
        if len(domains)!=1 or s['input_sha256'].get(domains[0])!=c['input_sha256'][domains[0]]:
            raise ValueError('catalog and selection native domain mismatch')
        paths=[cr,ar,sr,source,members,binary,Path(domains[0]),Path(__file__).resolve(),
               ROOT/'tools/native_rc_coverage/select_final_R_catalog.cpp',
               ROOT/'tools/charge_compiler/json.hpp',Path(__file__).with_name('common.py'),
               Path(__file__).with_name('compiled_charge.py'),Path(__file__).with_name('parallel_hash.py'),
               Path(__file__).with_name('resources.py')]
        pins={str(p):sha_prefetch(p,deadline=deadline) if p.stat().st_size>64*1024**2 else sha(p) for p in paths}
        if (pins[str(source)]!=c['artifacts'][str(source)] or
            pins[str(source)]!=v['input_sha256'][str(source)] or
            pins[str(members)]!=s['artifacts'][str(members)]):
            raise ValueError('audited source bytes changed')
        cfg=out/'config.json'
        save(cfg,dict(catalog=str(source),selection=str(members),output=str(out/'native'),deadline_uptime=deadline))
        save(out/'status.json',dict(state='partitioning_complete_catalog_compiled',release_qualified=False))
        execute([binary,cfg],out/'native.log',deadline,8)
        summary=json.loads((out/'native/summary.json').read_text())
        if summary['source_rows']!=v['native_tiles']:
            raise ValueError('source catalog row coverage mismatch')
        artifacts={str(p):sha_prefetch(p,deadline=deadline) for p in
            (out/'native/tile_catalog.jsonl',out/'native/superseded_tile_catalog.jsonl',out/'native/summary.json',cfg)}
        for p,h in pins.items():
            q=Path(p)
            if (sha_prefetch(q,deadline=deadline) if q.stat().st_size>64*1024**2 else sha(q))!=h:
                raise ValueError('input changed during catalog selection')
        save(out/'assessment.json',dict(**summary,input_sha256=pins,artifacts=artifacts,
             independent_partition_audit_complete=False,source_catalog=str(catalog),source_selection=str(selection)))
        save(out/'status.json',dict(state='final_R_catalog_partition_complete_pending_independent_audit',release_qualified=False))
        print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','audit','selection','binary','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
