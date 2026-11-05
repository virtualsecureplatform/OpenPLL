#!/usr/bin/env python3
"""Trace retained wire-R/device domains in the checked filled extraction view.

Preserve pre-resistance capacitance and native creation records for subsequent
operator reconciliation. A native RC export alone is not a complete qualified
physical model: signed-C attachment, substrate/FOM and numerical controls must
still be checked. One 12h budget includes waiting and assessment.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from common import ROOT,save,sha,verify
from status_store import update_root
sys.path.insert(0,str(ROOT/'verification/timing400'))
from run_DCO_domain_point_v3 import live_engines
TOP='Prototype400_FilledCapacitanceView'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--loading',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--original-owner',required=True,type=Path)
    a=p.parse_args();loading=a.loading.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original=json.loads(a.original_owner.read_text())
    budget_start=original.get('budget_started_utc',original['started_utc'])
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(budget_start)).total_seconds()
    remaining=43200-max(0,elapsed)
    assert remaining>0,'original check budget exhausted'
    deadline=time.monotonic()+remaining
    def expired(*_):raise TimeoutError('original 12h whole-check deadline exhausted')
    signal.signal(signal.SIGALRM,expired);signal.alarm(max(1,int(remaining)))
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,budget_started_utc=budget_start,original_owner=str(a.original_owner.resolve()),automatic_identical_retry=False))
    def status(state,**fields):
        value=dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**fields)
        save(out/'status.json',value);update_root('retained_rc_domain_trace',dict(value,path=str(out/'status.json')))
    try:
        while not (loading/'assessment.json').exists():
            if (loading/'status.json').exists():assert json.loads((loading/'status.json').read_text())['state']!='failed'
            assert time.monotonic()<deadline;status('waiting_for_fill_aware_loading_view');time.sleep(10)
        checked=json.loads((loading/'assessment.json').read_text());verify(checked['input_sha256']);verify(checked['artifacts'])
        assert checked['manufacturing_gds_unchanged'] and checked['floating_nodes_preserved']
        view=loading/'capacitance_view.gds';magic=ROOT/'build/timing400/magic_R_tile_domain_trace_623_001/bin/magic'
        private=ROOT/'build/timing450/pdk/sky130A';startup=private/'libs.tech/magic/sky130A.magicrc'
        trace=out/'trace';trace.mkdir()
        task=trace/'extract.tcl';task.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {view}
load {TOP}
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do resistance
extract do coupling
extract do adjust
extract do unique
extract warn all
extresist simplify off
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh infinite
ext2spice extresist off
ext2spice -f ngspice -o {trace}/pre_resistance.spice {TOP}.ext
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist on
ext2spice -f ngspice -o {trace}/retained_rc.spice {TOP}.ext
feedback save {trace}/feedback.txt
puts "FILLED_RETAINED_RC_NATIVE_COMPLETE"
}} error]}} {{puts stderr "FILLED_RC_ERROR=$error";quit -noprompt 1}}
quit -noprompt
''')
        pins={str(path):sha(path) for path in [Path(__file__).resolve(),Path(__file__).with_name('status_store.py'),magic,magic.parents[1]/'lib/magic/tcl/tclmagic.so',startup,private/'libs.tech/magic/sky130A.tech',loading/'assessment.json',view,task]}
        save(out/'input_manifest.json',dict(input_sha256=pins))
        env=dict(os.environ,PDK_ROOT=str(private.parent))
        for flag in ['OPENPLL_CAP_RC_SUBSTRATE','OPENPLL_CAP_TRACE_SUPPORT','OPENPLL_CAP_TRACE_FILE','OPENPLL_CAP_SURFACE_FILE','OPENPLL_CAP_KERNEL_FILE','OPENPLL_CAP_CLIP_INTERNAL']:env.pop(flag,None)
        env.update(OPENPLL_R_TILE_DOMAIN_TRACE='1',OPENPLL_R_RETAIN_MESH='1',
             OPENPLL_R_NODE_TRACE_FILE=str(trace/'R_provenance.log'),OPENPLL_R_SEGMENT_TRACE_FILE=str(trace/'R_segments.log'),
             OPENPLL_R_BIND_TRACE_FILE=str(trace/'R_bindings.log'),OPENPLL_SPICE_DEVICE_TRACE_FILE=str(trace/'SPICE_devices.log'))
        def limits():
            size=48*1024**3;resource.setrlimit(resource.RLIMIT_AS,(size,size))
        child=None
        with (ROOT/'build/timing400/guarded_native_admission.lock').open('a+') as lock:
            while time.monotonic()<deadline:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:time.sleep(2);continue
                live=live_engines()
                mem={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
                if not live and mem['MemAvailable']>=40*1024**3:
                    verify(pins)
                    with (trace/'extract.log').open('x') as log,(trace/'diagnostics.log').open('x') as err:
                        child=subprocess.Popen([str(magic),'-dnull','-noconsole','-rcfile',str(startup),str(task)],
                             cwd=trace,env=env,stdout=log,stderr=err,start_new_session=True,preexec_fn=limits)
                    status('retained_rc_native_running',native_pid=child.pid);break
                fcntl.flock(lock,fcntl.LOCK_UN);status('queued_for_native_capacity',native_before=live);time.sleep(5)
        assert child is not None,'native capacity wait exhausted budget'
        try:code=child.wait(timeout=max(.01,deadline-time.monotonic()))
        except BaseException:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            raise
        assert code==0 and 'FILLED_RETAINED_RC_NATIVE_COMPLETE' in (trace/'extract.log').read_text()
        for name in ('pre_resistance.spice','retained_rc.spice',TOP+'.ext',TOP+'.res.ext','R_provenance.log','R_bindings.log','SPICE_devices.log'):
            assert (trace/name).is_file() and (trace/name).stat().st_size>0,name
        counts={prefix:0 for prefix in ('R','C','X','M')}
        for line in (trace/'retained_rc.spice').open():
            prefix=line[:1].upper()
            if prefix in counts:counts[prefix]+=1
        assert counts['R']>0 and counts['C']>0 and counts['X']+counts['M']>0
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,native_rc_export_completed=True,retained_native_cards=counts,
             pre_resistance_capacitance_preserved=True,domain_creation_records_preserved=True,
             all_wire_domains_reconciled=False,signed_capacitance_attachment_qualified=False,
             fom_substrate_coverage_qualified=False,physical_domain_complete=False,
             prototype_handoff_qualified=False,release_qualified=False,
             artifacts={str(p):sha(p) for p in trace.rglob('*') if p.is_file()}))
        status('retained_rc_native_terminal_pending_domain_reconciliation',retained_native_cards=counts)
    except BaseException as e:status('failed',reason=repr(e));raise


if __name__=='__main__':main()
