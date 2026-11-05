#!/usr/bin/env python3
"""Read-only first-cycle comparison; no numerical-domain qualification or verdict."""
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process


def parse_prefix(raw):
    raw=raw[:raw.rfind(b'\n')+1]
    lines=raw.decode().splitlines()
    if not lines:return [],raw
    assert lines[0].split()==['Index','TIME','V(PLLOUT)','I(VVPWR)']
    rows=[];terminal=False
    for line in lines[1:]:
        if not line.strip():continue
        if 'End of Xyce(TM) Simulation' in line:
            assert not terminal;terminal=True;continue
        fields=line.split();assert not terminal and len(fields)==4 and int(fields[0])==len(rows)
        row=tuple(map(float,fields[1:]));assert all(map(math.isfinite,row))
        assert (not rows and row[0]==0) or (rows and row[0]>rows[-1][0])
        rows.append(row)
    return rows,raw


def edges(rows):
    found={'rising':[],'falling':[]}
    for a,b in zip(rows,rows[1:]):
        direction='rising' if a[1]<.9<=b[1] else 'falling' if a[1]>.9>=b[1] else None
        if direction:
            edge=a[0]+(.9-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if edge>=5.05e-9:found[direction].append(edge)
    return found


def compare(old,new):
    original,current=edges(old),edges(new)
    if any(len(e[d])<4 for e in (original,current) for d in original):return None
    records=[]
    for direction in original:
        a,b=original[direction][:4],current[direction][:4]
        first=[y-x for x,y in zip(a,b)]
        periods=[]
        for index in range(3):
            p,q=a[index+1]-a[index],b[index+1]-b[index]
            assert p>0 and q>0
            periods.append(dict(period_index=index,reference_period_s=p,candidate_period_s=q,
                period_difference_s=q-p,frequency_difference_Hz=1/q-1/p,
                frequency_difference_ppm_of_reference=(p/q-1)*1e6))
        records.append(dict(direction=direction,reference_edges_s=a,candidate_edges_s=b,
            signed_edge_differences_s=first,maximum_absolute_edge_difference_s=max(map(abs,first)),periods=periods))
    return records


def main():
    root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
    point=base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001'
    prior=base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002'
    audit_path=base/'retained_Gear_before_bounded_reuse_audit_001/assessment.json'
    audit=json.loads(audit_path.read_text());assert audit['controlled_interruption_verified']
    for p,sha in audit['input_sha256'].items():assert digest(Path(p))==sha,p
    old,old_raw=parse_prefix((prior/'point.cir.prn').read_bytes())
    owner=json.loads((point/'owner.json').read_text());deadline=owner['deadline_uptime']
    launched=json.loads((point/'launch.json').read_text());identity=process(launched['pid'])
    assert identity['live'] and identity['argv'][-1]==str(point/'point.cir')
    assert (point/'point.cir').read_bytes()==(prior/'point.cir').read_bytes()
    out=base/'bounded_reuse_DCO_cycle_comparison_001';out.mkdir(exist_ok=False)
    pins={str(p):digest(p) for p in (Path(__file__).resolve(),audit_path,point/'owner.json',point/'launch.json',point/'point.cir',prior/'point.cir.prn')}
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),native_identity=identity,
        deadline_uptime=deadline,native_started_stopped_or_retried=False,input_sha256=pins))
    wave=Path(str(point/'point.cir')+'.prn')
    while True:
        current_identity=process(launched['pid']);live=current_identity['live'] and current_identity['argv']==identity['argv']
        new,raw=parse_prefix(wave.read_bytes()) if wave.exists() else ([],b'')
        result=compare(old,new)
        if result is not None:
            (out/'reference_prefix.prn').write_bytes(old_raw);(out/'candidate_prefix.prn').write_bytes(raw)
            for p,sha in pins.items():assert digest(Path(p))==sha,p
            save(out/'assessment.json',dict(input_sha256=pins,
                prefix_sha256={str(p):digest(p) for p in (out/'reference_prefix.prn',out/'candidate_prefix.prn')},
                comparisons=result,source_native_live_at_observation=live,periods_compared_per_direction=3,
                comparison_uses_unsettled_startup_cycles=True,comparison_acceptance_threshold_selected=False,
                full_trajectory_accuracy_qualified=False,frequency_convergence_qualified=False,
                native_case_verdict_inferred=False,release_qualified=False,adopted=False))
            save(out/'status.json',dict(state='completed_startup_cycle_comparison',release_qualified=False));return
        if not live or time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
            save(out/'status.json',dict(state='incomplete_cycle_comparison',source_native_live=live,observed_edges=edges(new),release_qualified=False));return
        save(out/'status.json',dict(state='waiting_for_three_complete_periods_per_direction',source_native_live=True,
            observed_edges=edges(new),deadline_uptime=deadline,release_qualified=False))
        time.sleep(min(30,max(.01,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))


if __name__=='__main__':main()
