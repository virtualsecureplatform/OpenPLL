"""Apply mutation-site coverage only to a completed full-layout support audit."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from audit_magic_ground_support_coverage import coverage,support_counts


def run(audit,engine,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((audit/'status.json').read_text())['state']
            if state=='resolved_trace_support_diagnostics_complete' and (audit/'assessment.json').exists():break
            if state=='stopped_without_qualification':raise RuntimeError('support audit stopped')
            owner=json.loads((audit/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('support audit owner missing')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('completed audit observation deadline')
            save(output/'status.json',dict(state='waiting_for_completed_full_layout_support_audit',release_ready=False));time.sleep(10)
        receipt=audit/'assessment.json';a=json.loads(receipt.read_text());engine_receipt=engine/'assessment.json';e=json.loads(engine_receipt.read_text());instrumentation=engine/'instrumentation.json'
        if not a['completed_native_trace_audited'] or a['input_sha256'].get(str(engine_receipt))!=sha(engine_receipt) or e['artifacts'].get(str(instrumentation))!=sha(instrumentation):raise ValueError('completed audit and pinned observer inventory required')
        paths=[receipt,engine_receipt,instrumentation,audit/'packets/ground_support.jsonl',Path(__file__).resolve(),Path(__file__).with_name('audit_magic_ground_support_coverage.py')]
        pins={str(p):sha(p) for p in paths}
        save(output/'inputs.json',dict(input_sha256=pins,CPU=29,memory_GiB=2,resource_queue_cap_s=21600,release_ready=False));save(output/'status.json',dict(state='waiting_for_global_CPU_RAM_budget',release_ready=False))
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+21600):
            verify(a['input_sha256']);verify(a['artifacts']);verify(e['input_sha256']);verify(e['artifacts']);verify(pins)
            inventory=json.loads(instrumentation.read_text())['direct_ground_mutation_inventory']
            result=coverage(inventory,a['ground_ledger'],support_counts(audit/'packets/ground_support.jsonl'),a['ground_overlap'],a['ground_halo'],a['ground_tail']);verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={},**result,completed_full_layout_support_coverage_checked=True,native_simulation_allowed=False))
        save(output/'status.json',dict(state='full_layout_ground_support_coverage_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),native_children_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['audit','engine','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.audit.resolve(),a.engine.resolve(),a.output.resolve())
