#!/usr/bin/env python3
"""Record owned capacitance kernels for the exact filled R-domain geometry.

Use the existing, controlled extractor; compare native C/device cards against
its exact untraced extraction before compiling signed local energy operators.
This is model construction, not global passivity or transient qualification.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import resource
import shlex
import signal
import subprocess
import sys
import time
from common import ROOT,save,sha,verify
from status_store import update_root
sys.path.insert(0,str(ROOT/'verification/timing400'))
from run_DCO_domain_point_v3 import live_engines
from check_isolated_magic_stock_v3 import matrix,devices
TOP='Prototype400_FilledCapacitanceView'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('domain','loading','output'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--original-owner',required=True,type=Path)
    p.add_argument('--upstream-status',action='append',type=Path,default=[])
    a=p.parse_args();domain=a.domain.resolve();loading=a.loading.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original=json.loads(a.original_owner.read_text())
    budget_start=original.get('budget_started_utc',original['started_utc'])
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(budget_start)).total_seconds()
    remaining=43200-max(0,elapsed)
    assert remaining>0,'original check budget exhausted'
    deadline=time.monotonic()+remaining
    def expired(*_):raise TimeoutError('original 12h whole-check deadline exhausted')
    signal.signal(signal.SIGALRM,expired);signal.alarm(max(1,int(remaining)))
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,budget_started_utc=budget_start,original_owner=str(a.original_owner.resolve()),automatic_identical_retry=False))
    def status(state,**kw):
        value=dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**kw)
        save(out/'status.json',value);update_root('owned_capacitance_trace',dict(value,path=str(out/'status.json')))
    try:
        while not (domain/'assessment.json').exists():
            for upstream in a.upstream_status:
                if upstream.exists():
                    state=json.loads(upstream.read_text())['state']
                    assert state not in ('failed','timeout_inconclusive') and not state.endswith('_nonpass'),str(upstream)
            if (domain/'status.json').exists():assert json.loads((domain/'status.json').read_text())['state']!='failed'
            assert time.monotonic()<deadline;status('waiting_for_retained_domain_reference');time.sleep(10)
        proof=json.loads((domain/'assessment.json').read_text());verify(proof['input_sha256']);verify(proof['artifacts'])
        assert proof['native_rc_export_completed']
        base=ROOT/'build/timing400/release_001';controls=base/'magic_C_owner_controls_001/assessment.json'
        check=json.loads(controls.read_text());verify(check['input_sha256']);verify(check.get('artifacts',{}));assert check['all12_owner_trace_native_equivalence_and_accounting_controls_passed']
        binary=ROOT/'build/timing400/magic_C_owner_trace_623_001/bin/magic'
        private=ROOT/'build/timing450/pdk/sky130A';startup=private/'libs.tech/magic/sky130A.magicrc'
        trace=out/'trace';trace.mkdir();reference=domain/'trace'
        task=trace/'extract.tcl'
        source=(reference/'extract.tcl').read_text()
        start=source.index('extresist all\n');end=source.index('puts "FILLED_RETAINED_RC_NATIVE_COMPLETE"')
        source=source[:start]+f'feedback save {trace}/feedback.txt\n'+source[end:]
        source=source.replace(str(reference),str(trace)).replace('FILLED_RETAINED_RC_NATIVE_COMPLETE','FILLED_OWNER_C_NATIVE_COMPLETE')
        task.write_text(source)
        pins={str(path):sha(path) for path in [Path(__file__).resolve(),Path(__file__).with_name('status_store.py'),binary,
             binary.parents[1]/'lib/magic/tcl/tclmagic.so',startup,private/'libs.tech/magic/sky130A.tech',
             controls,domain/'assessment.json',reference/'extract.tcl',reference/'pre_resistance.spice',reference/(TOP+'.ext'),
             loading/'assessment.json',loading/'capacitance_view.gds',task,
             a.original_owner.resolve(),ROOT/'verification/timing400/check_isolated_magic_stock_v3.py']}
        save(out/'input_manifest.json',dict(input_sha256=pins))
        env={k:v for k,v in os.environ.items() if not k.startswith('OPENPLL_')}
        env.update(PDK_ROOT=str(private.parent),OPENPLL_CAP_RC_SUBSTRATE='1',OPENPLL_CAP_TRACE_SUPPORT='1',
             OPENPLL_CAP_TRACE_FILE=str(trace/'contributions.log'),OPENPLL_CAP_SURFACE_FILE=str(trace/'surfaces.log'),
             OPENPLL_CAP_KERNEL_FILE=str(trace/'kernels.log'),OPENPLL_CAP_OWNER_FILE=str(trace/'owners.log'))
        def limits():
            value=48*1024**3;resource.setrlimit(resource.RLIMIT_AS,(value,value))
        child=None
        with (ROOT/'build/timing400/guarded_native_admission.lock').open('a+') as lock:
            while time.monotonic()<deadline:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:time.sleep(2);continue
                live=live_engines();mem={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
                if not live and mem['MemAvailable']>=40*1024**3:
                    verify(pins)
                    with (trace/'extract.log').open('x') as log,(trace/'diagnostics.log').open('x') as err:
                        child=subprocess.Popen([str(binary),'-dnull','-noconsole','-rcfile',str(startup),str(task)],cwd=trace,
                            env=env,stdout=log,stderr=err,start_new_session=True,preexec_fn=limits)
                    status('owned_capacitance_native_running',native_pid=child.pid);break
                fcntl.flock(lock,fcntl.LOCK_UN);status('queued_for_native_capacity',native_before=live);time.sleep(5)
        assert child is not None,'native capacity budget exhausted'
        try:code=child.wait(timeout=max(.01,deadline-time.monotonic()))
        except BaseException:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            raise
        assert code==0 and 'FILLED_OWNER_C_NATIVE_COMPLETE' in (trace/'extract.log').read_text()
        status('checking_native_capacitance_equivalence')
        assert matrix(reference/'pre_resistance.spice')==matrix(trace/'pre_resistance.spice')
        assert devices(reference/(TOP+'.ext'))==devices(trace/(TOP+'.ext'))
        ids={}
        for line in (trace/'contributions.log').open():
            if line.startswith('OPENPLL_ID '):
                f=shlex.split(line);assert len(f)==4 and f[1] not in ids and f[3] in ('0','1')
                ids[f[1]]='@SUBSTRATE' if f[3]=='1' else f[2]
        assert list(ids.values()).count('@SUBSTRATE')==1
        save(trace/'node_ids.json',ids);verify(pins)
        # Native generation and controlled comparisons complete here. The next
        # independently bounded check uses the multicore, streaming C++ compiler.
        save(out/'assessment.json',dict(input_sha256=pins,native_C_and_device_cards_unchanged=True,
             native_owned_trace_complete=True,signed_owned_operators_compiled=False,
             original_floating_nodes_preserved=True,full_C_energy_matrix_assembled=False,global_passivity_qualified=False,
             fom_substrate_coverage_qualified=False,physical_domain_complete=False,prototype_handoff_qualified=False,release_qualified=False,
             artifacts={str(path):sha(path) for path in out.rglob('*') if path.is_file() and path.name not in ('status.json','assessment.json')}))
        status('native_owned_trace_terminal_pending_compiled_operators')
    except BaseException as e:status('failed',reason=repr(e));raise


if __name__=='__main__':main()
