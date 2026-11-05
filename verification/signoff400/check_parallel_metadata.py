#!/usr/bin/env python3
"""Check parallel metadata on the full retained input and serial reference."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import identity,lease


def run(a):
    compiled,out=a.compiled.resolve(),a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original=json.loads((compiled/'owner.json').read_text());deadline=original['deadline_uptime']
    trace=Path(original['source'])/'trace';source=trace/'surfaces.log';reference=compiled/'trace_metadata.json'
    manifest=json.loads((compiled/'input_manifest.json').read_text())
    shard=compiled/'worker_0/assessment.json';proof=json.loads(shard.read_text())
    controls=a.controls.resolve()/'assessment.json';control=json.loads(controls.read_text())
    if control['status']!='pass' or control['binary_sha256']!=sha(a.binary.resolve()):
        raise ValueError('matching completed metadata controls required')
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),original_deadline_uptime=deadline,
        original_compilation_unchanged=True,total_budget_restarted=False,threads=8))
    start=time.monotonic()
    with lease(8,8,deadline):
        save(out/'status.json',dict(state='hashing_retained_surface_and_reference',release_qualified=False))
        paths=[compiled/'owner.json',compiled/'input_manifest.json',shard,controls,source,reference,a.binary.resolve(),
            ROOT/'tools/charge_compiler/metadata_parallel.cpp',ROOT/'tools/charge_compiler/main_stream_ledger.cpp',
            ROOT/'tools/charge_compiler/json.hpp',Path(__file__).resolve(),Path(__file__).with_name('parallel_hash.py')]
        pins={str(p):sha_prefetch(p,deadline=deadline) for p in paths}
        if pins[str(source)]!=manifest['input_sha256'][str(source)] or pins[str(reference)]!=proof['input_sha256'][str(reference)]:
            raise ValueError('surface input or original serial metadata changed')
        for name in ('main_stream_ledger.cpp','json.hpp'):
            p=ROOT/'tools/charge_compiler'/name
            if pins[str(p)]!=manifest['input_sha256'][str(p)]:raise ValueError('original serial parser source changed')
        save(out/'input_manifest.json',dict(input_sha256=pins,observed_utc=datetime.now(timezone.utc).isoformat()))
        save(out/'status.json',dict(state='running_eight_thread_full_surface_metadata',release_qualified=False))
        t=time.monotonic()
        execute([a.binary.resolve(),trace,out/'metadata.json',deadline,8,'parallel'],out/'native.log',deadline,4)
        elapsed=time.monotonic()-t
        if (out/'metadata.json').read_bytes()!=reference.read_bytes():
            raise ValueError('full parallel metadata differs from completed serial reference')
        for p,h in pins.items():
            if sha_prefetch(Path(p),deadline=deadline)!=h:raise ValueError('metadata input changed during control')
        metadata=json.loads((out/'metadata.json').read_text())
        save(out/'assessment.json',dict(input_sha256=pins,
            artifacts={str(out/n):sha(out/n) for n in ('metadata.json','native.log','input_manifest.json')},
            complete_native_surface_bytes=source.stat().st_size,threads=8,
            full_metadata_literal_byte_identity=True,native_parallel_elapsed_s=elapsed,
            total_check_elapsed_s=time.monotonic()-start,measured_isolated_speedup=False,
            native_type_names=len(metadata['types']),native_plane_names=len(metadata['planes']),
            native_plane_residue_mappings=len(metadata['residues']),production_adopted=False,
            physical_RC_qualified=False,release_qualified=False))
        save(out/'status.json',dict(state='full_parallel_metadata_equivalence_pass',release_qualified=False))
        print(json.dumps(dict(bytes=source.stat().st_size,native_elapsed_s=elapsed,full_metadata_literal_byte_identity=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('compiled','controls','binary','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
