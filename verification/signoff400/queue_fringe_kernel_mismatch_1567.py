"""Locate an unqualified counterexample in the closed native trace, without rerunning Magic."""
import json,os,time
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute

def run():
    output=ROOT/'build/signoff400/selected_keeper_fringe_kernel_mismatch_1567'
    owner=output/'owner.json'
    with owner.open('x') as stream:
        json.dump(dict(pid=os.getpid(),birth=identity(os.getpid())),stream)
    status=output/'status.json'
    try:
        source=ROOT/'build/signoff400/selected_keeper_ground_local_compressed_trace_1437'
        receipt=source/'assessment.json';record=json.loads(receipt.read_text())
        archive=source/'trace_archive.json';retention=json.loads(archive.read_text())
        trace=Path(retention['source']);before=trace.stat()
        fingerprint=lambda s:[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
        if (record['artifacts'][str(archive)]!=sha(archive)
                or not record['native_process_completed']
                or not record['lossless_trace_archive_roundtrip_verified']
                or retention['uncompressed_sha256']!=record['artifacts'][str(source/'coupling.jsonl')]
                or before.st_size!=retention['uncompressed_bytes']
                or before.st_mtime_ns>archive.stat().st_mtime_ns):
            raise ValueError('completed, archived, unchanged-size source required')
        binary=output/'scanner';code=ROOT/'verification/signoff400/capture_fringe_kernel_mismatch.cpp'
        save(output/'inputs.json',dict(input_sha256={str(p):sha(p) for p in [receipt,archive,binary,code,Path(__file__).resolve()]},
            source_trace_sha256_from_verified_archive=retention['uncompressed_sha256'],
            source_trace_fingerprint=fingerprint(before),source_trace_rehashed_in_this_diagnostic=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
        save(status,dict(state='waiting_for_resources',release_ready=False))
        with lease(1,.125,deadline):
            save(status,dict(state='scanning_closed_trace',release_ready=False))
            execute(['taskset','-c','19',str(binary),str(trace),str(output/'fringe_group.jsonl')],
                    output/'scan.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+1800),memory_gib=.125)
        if fingerprint(trace.stat())!=fingerprint(before):raise ValueError('trace changed during scan')
        rows=[json.loads(line) for line in (output/'fringe_group.jsonl').read_text().splitlines()]
        if rows[0]['kind']!='fringe_rule_begin' or rows[-1]['kind']!='fringe_rule_end':
            raise ValueError('complete group required')
        fields=['reference_length','boundary','direction','coupling_multiplier_hex','substrate_multiplier_hex']
        changed=[dict(record=i,fields={k:dict(begin=rows[0][k],leaf=row[k]) for k in fields if rows[0][k]!=row[k]})
                 for i,row in enumerate(rows) if row['kind']=='fringe_shield_leaf']
        changed=[v for v in changed if v['fields']]
        if not changed:raise ValueError('scanner did not preserve a mismatch')
        save(output/'assessment.json',dict(changed_records=changed,records=len(rows),
            artifacts={str(output/name):sha(output/name) for name in ['fringe_group.jsonl','scan.log','inputs.json']},
            native_trace_complete=True,whole_trace_reaudited=False,source_trace_rehashed_in_this_diagnostic=False,
            diagnostic_only=True,extractor_fix_qualified=False,release_ready=False))
        save(status,dict(state='completed_diagnostic_counterexample',release_ready=False))
    except Exception as error:
        save(status,dict(state='stopped_without_qualification',reason=repr(error),release_ready=False))
        raise

if __name__=='__main__':run()
