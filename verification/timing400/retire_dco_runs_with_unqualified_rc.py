#!/usr/bin/env python3
"""Retire four diagnostic DCO runs after their actual RC model fails audit.

Preserve decks, inputs, logs and partial waveforms. Do not retry, mutate source
models or reset any check budget. Free native capacity for existing admitted
work; physical tuning/calibration decisions based on this model remain invalid.
"""
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import time
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001'
    audit_path=base/'active_dco_rc_capacitance_audit_001/assessment.json'
    audit=json.loads(audit_path.read_text())
    assert audit['actual_live_DCO_source_audited'] and not audit['same_threshold_capacitor_matrix_preserved']
    assert audit['changed_capacitor_branch_pairs']==1799 and audit['completely_lost_capacitor_branch_pairs']==256
    model=ROOT/'build/timing450/dco_c1_fine_load_001/rcx_160/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160.reduced.spice'
    assert sha(model)==audit['input_sha256'][str(model)]
    jobs=[(3883557,'dco_duration_c1_f128_160ns_resetfix_001','duration.spice'),
        (3883676,'dco_duration_c1_f247_160ns_resetfix_001','duration.spice'),
        (3903126,'tt100_coarse14_f247_range_001','range.spice'),
        (3903154,'tt100_coarse14_f8_range_001','range.spice')]
    out=base/'unqualified_dco_RC_retirement_001';out.mkdir(exist_ok=False)
    files=[Path(__file__).resolve(),audit_path,model]
    records=[]
    with (ROOT/'build/timing400/guarded_native_admission.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for pid,name,deck in jobs:
            proc=Path('/proc')/str(pid);path=base/name/deck
            assert (proc/'comm').read_text().strip()=='Xyce'
            argv=[x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
            assert argv[-1]==str(path) and os.getpgid(pid)==pid
            text=path.read_text()
            assert str(model) in re.findall(r'^\.include "([^"]+)"',text,re.M)
            records.append(dict(pid=pid,deck=str(path),argv=argv,reason='Actual RC backannotation failed same-threshold capacitor preservation',
                deck_sha256=sha(path),model_sha256=sha(model),original_owner=json.loads((base/name/'owner.json').read_text())))
            files += [path,base/name/'owner.json',base/name/'input_manifest.json']
        save(out/'intent.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),jobs=records,
            audit=str(audit_path),automatic_identical_retry=False,original_deadlines_retained=True))
        for row in records:os.killpg(row['pid'],signal.SIGTERM)
        until=time.monotonic()+10
        def running(pid):
            p=Path('/proc')/str(pid)
            try:return (p/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
            except FileNotFoundError:return False
        while any(running(row['pid']) for row in records) and time.monotonic()<until:time.sleep(.1)
        for row in records:
            if running(row['pid']):os.killpg(row['pid'],signal.SIGKILL)
        until=time.monotonic()+5
        while any(running(row['pid']) for row in records) and time.monotonic()<until:time.sleep(.1)
        assert not any(running(row['pid']) for row in records)
        for row in records:
            row['native_stopped_verified']=True
            directory=Path(row['deck']).parent
            waves=list(directory.glob('*.prn'))
            row['partial_waveforms']=[str(p) for p in waves]
            for wave in waves:
                with wave.open('rb') as stream:
                    stream.seek(max(0,wave.stat().st_size-4096));lines=stream.read().split(b'\n')[:-1]
                complete=[x.split() for x in lines if x.split() and x.split()[0].isdigit()]
                if complete:row['last_complete_simulation_time_ns']=float(complete[-1][1])*1e9
            save(directory/'unqualified_rc_retirement.json',dict(retirement_receipt=str(out/'assessment.json'),
                reason=row['reason'],native_stopped_verified=True,
                partial_waveforms_retained=True,range_or_calibration_decision_qualified=False,
                automatic_identical_retry=False,original_deadline_retained=True,release_qualified=False))
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},
        artifacts={str(out/'intent.json'):sha(out/'intent.json')},jobs=records,
        retired_native_jobs=4,all_native_processes_stopped_verified=True,
        source_inputs_and_partial_results_retained=True,original_check_deadlines_retained=True,
        live_model_disqualified_for_physical_range_and_calibration=True,
        prior_completed_frequencies_remain_model_diagnostics=True,
        no_identical_native_retry_started=True,new_analog_jobs_added=0,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Retired all4 DCO diagnostics with failed RC model; partial results retained; no retry or deadline reset.')


if __name__=='__main__':main()
