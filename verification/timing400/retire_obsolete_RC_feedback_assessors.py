#!/usr/bin/env python3
"""Retire queued old-warning assessors after direct RC-context geometry evidence.

Only the old nominal/maximum waiting Python collectors are signalled through
pidfds. Require replacement collectors live, source work incomplete and the
old collector still waiting with no assessment child. Native CAD and its
original absolute deadlines are untouched. Preserve the failed minimum audit.
"""
from pathlib import Path
import json,os,signal,time
from datetime import datetime,timezone
from run_dco_qualification import ROOT,sha,save


def state(pid):
    p=Path('/proc')/str(pid)
    try:return dict(pid=pid,stat=(p/'stat').read_text().rsplit(')',1)[1].split()[0],
        argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x])
    except (FileNotFoundError,ProcessLookupError):return dict(pid=pid,stat=None,argv=[])


def main():
    base=ROOT/'build/timing400/release_001';proof=base/'RC_substrate_capacitance_collection_002/min/feedback/assessment.json'
    data=json.loads(proof.read_text());assert data['full_corner_warning_classification_passed'] and data['full_feedback_entries']==2288
    assert data['native_diode_position_area_perimeter_and_body_matches']==726
    out=base/'RC_substrate_old_feedback_assessor_retirement_001';out.mkdir(exist_ok=False)
    rows=[];paths=[Path(__file__).resolve(),proof,base/'RC_substrate_capacitance_collection_001/min/feedback.log']
    for corner in ['nom','max']:
        old=base/'RC_substrate_capacitance_collection_001'/corner
        new=base/'RC_substrate_capacitance_collection_002'/corner
        source=base/'poly_metal_full_RC_substrate_capacitance_001'/corner
        owner=json.loads((old/'owner.json').read_text());new_owner=json.loads((new/'owner.json').read_text())
        assert owner['deadline_uptime']==new_owner['deadline_uptime']==3136114.566309955
        status=json.loads((old/'status.json').read_text());assert status['state']=='waiting_for_existing_extraction'
        assert 'assessment_pid' not in status and not (source/'native_completion.json').exists()
        pid=owner['runner_pid'];replacement=state(new_owner['runner_pid'])
        assert replacement['stat'] not in [None,'Z'] and 'verification/timing400/collect_full_layout_RC_substrate_capacitance_v2.py' in replacement['argv']
        fd=os.pidfd_open(pid)
        try:
            before=state(pid)
            assert before['stat'] not in [None,'Z'] and 'verification/timing400/collect_full_layout_RC_substrate_capacitance.py' in before['argv']
            assert before['argv'][-2:]==['--corner',corner]
            signal.pidfd_send_signal(fd,signal.SIGTERM)
        finally:os.close(fd)
        for _ in range(20):
            after=state(pid)
            if after['stat'] in [None,'Z']:break
            time.sleep(.1)
        assert after['stat'] in [None,'Z']
        retirement=dict(corner=corner,old_collector=before,after=after,replacement=replacement,
            original_deadline_uptime=owner['deadline_uptime'],native_jobs_signalled=0,
            reason='Expected3014 warning entries conflicts with validated native RC-context2288 decap diagnostics; all726 diodes are checked directly.')
        save(old/'retirement.json',retirement)
        save(old/'status.json',dict(state='obsolete_feedback_assessor_retired',replacement=str(new),native_jobs_signalled=0,
            deadline_uptime=owner['deadline_uptime'],total_budget_restarted=False,release_qualified=False))
        rows.append(retirement);paths.extend([old/'owner.json',new/'owner.json',old/'retirement.json'])
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},artifacts={},
        observed_utc=datetime.now(timezone.utc).isoformat(),retired_collectors=rows,
        replacement_collectors_verified_live=True,native_CAD_or_analog_jobs_signalled=0,
        original_deadlines_unchanged=True,automatic_native_retries=0,release_qualified=False))
    print('Retired2 obsolete waiting assessors; verified replacements live, no native jobs signalled, original deadlines retained.')


if __name__=='__main__':main()
