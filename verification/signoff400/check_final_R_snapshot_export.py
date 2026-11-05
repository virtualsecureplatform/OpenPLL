#!/usr/bin/env python3
"""Reconcile final full-pass R snapshots against the actual overwritten export."""
import argparse
import json
from pathlib import Path
import re
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    domain=a.domain.resolve();receipt=domain/'assessment.json'
    report=json.loads(receipt.read_text());trace=domain/'trace'
    log=trace/'extract.log';recipe=trace/'extract.tcl';provenance=trace/'R_provenance.log'
    exports=list(trace.glob('*.res.ext'))
    if len(exports)!=1:raise ValueError('unique final native resistance export required')
    native=ROOT/'build/timing400/magic_R_tile_domain_source_001'
    paths=[receipt,log,recipe,provenance,exports[0],a.binary.resolve(),
           ROOT/'tools/native_rc_coverage/check_final_R_snapshots_v2.cpp',
           ROOT/'tools/charge_compiler/json.hpp',native/'extract/ExtMain.c',
           native/'resis/ResRex.c',native/'resis/ResPrint.c',native/'resis/resis.h',
           Path(__file__).resolve()]
    with lease(1,8,deadline):
        pins={str(p):sha(p) for p in paths}
        for p in (log,recipe,provenance,exports[0]):
            if report['artifacts'].get(str(p))!=pins[str(p)]:
                raise ValueError('native source artifact differs from producer: '+str(p))
        counts=list(map(int,re.findall(r'^Nets output: (\d+) ',log.read_text(),re.M)))
        if len(counts)!=2 or counts[0]<=0 or counts[1]<=counts[0]:
            raise ValueError('expected automatic partial pass followed by explicit full pass')
        code=(native/'resis/ResRex.c').read_text()
        if 'PaOpen(outfile, "w", ".res.ext"' not in code:
            raise ValueError('native output overwrite semantics differ')
        if 'if (ExtOptions & EXT_DOEXTRESIST)' not in (native/'extract/ExtMain.c').read_text():
            raise ValueError('automatic resistance pass source differs')
        text=recipe.read_text()
        if not text.index('extract do resistance')<text.index('extract all')<text.index('extresist all')<text.index('ext2spice extresist on'):
            raise ValueError('native export command ordering differs')
        save(out/'input_manifest.json',dict(input_sha256=pins,pass_output_counts=counts))
        save(out/'status.json',dict(state='checking_final_native_R_snapshot_multisets',release_qualified=False))
        execute([a.binary.resolve(),provenance,exports[0],counts[0],out/'native_result.json'],
                out/'native.log',deadline,8)
        result=json.loads((out/'native_result.json').read_text())
        if result['selected_group_count']!=counts[1]:
            raise ValueError('final full-pass group count mismatch')
        for p,h in pins.items():
            if sha(Path(p))!=h:raise ValueError('input changed during check')
        save(out/'assessment.json',dict(input_sha256=pins,
            artifacts={str(out/n):sha(out/n) for n in ('native_result.json','native.log','input_manifest.json')},
            selected_group_count=counts[1],superseded_prefix_group_count=counts[0],
            native_final_R_export_snapshot_mapping_verified=True,
            final_res_ext_node_and_resistor_multisets_match=True,
            historical_raw_snapshots_retained=True,full_C_attachment_qualified=False,
            physical_RC_qualified=False,release_qualified=False))
        save(out/'status.json',dict(state='final_native_R_snapshot_export_verified',release_qualified=False))
        print(json.dumps({k:v for k,v in result.items() if k!='selected_groups'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('domain','binary','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
