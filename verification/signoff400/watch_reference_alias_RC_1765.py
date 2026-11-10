"""Fail fast only on owned native geometry failures; never retry or consume partial data."""
import json,time,os,signal,datetime
from runtime_common import ROOT,save,sha
from resources import identity

def run():
    source=ROOT/'build/signoff400/selected_reference_alias_full_RC_1764';out=ROOT/'build/signoff400/selected_reference_alias_RC_watch_1765';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    owner=json.loads((source/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+50000
    bad=('OPENPLL_RC_BREAK_BOUNDS','OPENPLL_RC_NEGATIVE_AREA','OPENPLL_RC_BAD_AREA','OPENPLL_RC_BAD_CAP_BUDGET','OPENPLL_RC_EMPTY_CROSSPLANE_OVERLAP','OPENPLL_RC_EMPTY_DRIVER_OVERLAP',"Couldn't find wire","Couldn't find device",'Error in extracting node','OPENPLL_RC_REFERENCE_ERROR')
    position=0
    save(out/'inputs.json',dict(input_sha256={str(__file__):sha(__file__),str(source/'owner.json'):sha(source/'owner.json')},watched_prefixes=bad,automatic_retry=False,partial_native_data_accepted=False))
    while time.clock_gettime(time.CLOCK_BOOTTIME)<deadline:
        failure=None;log=source/'native.log'
        if log.exists():
            with log.open() as stream:
                stream.seek(position)
                while True:
                    line=stream.readline()
                    if not line:break
                    if line.startswith(bad) or any(t in line.lower() for t in ['orphaned node','missing terminal','not extracted as network','force label but no drive']):failure=line.strip();break
                position=stream.tell()
        if failure:
            worker=json.loads((source/'native.process.json').read_text());pid=worker['pid']
            if identity(pid)!=worker['birth']:raise RuntimeError('failed worker ended before observation; do not signal a reused PID')
            from pathlib import Path
            command=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
            if os.getpgid(pid)!=worker['process_group'] or 'magic_reference_alias_1757' not in command or 'selected_reference_alias_full_RC_1764' not in command:raise ValueError('owned native worker identity mismatch')
            receipt=dict(stopped_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),worker=worker,command=command,reason='confirmed native geometry or conductor extraction failure',native_failure=failure,user_cancellation=False,partial_native_data_accepted=False,automatic_retry=False)
            save(out/'diagnostic_stop_receipt.json',receipt)
            os.killpg(worker['process_group'],signal.SIGTERM)
            save(out/'status.json',dict(state='stopped_owned_invalid_native_RC',native_failure=failure,release_ready=False));return
        state=json.loads((source/'status.json').read_text())
        if (source/'assessment.json').exists():
            save(out/'assessment.json',dict(source_receipt_sha256=sha(source/'assessment.json'),native_geometry_failure_observed=False,log_bytes_observed=position,full_export_audit_required=True,release_ready=False))
            save(out/'status.json',dict(state='native_worker_completed_geometry_audit_pending',release_ready=False));return
        if state['state']=='stopped_without_qualification':
            save(out/'status.json',dict(state='source_stopped_without_qualification',source_status=state,release_ready=False));return
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('source owner ended without terminal receipt')
        save(out/'status.json',dict(state='watching_live_owned_native_worker',log_bytes_observed=position,release_ready=False))
        time.sleep(10)
    raise TimeoutError('geometry watch observation deadline')
if __name__=='__main__':run()
