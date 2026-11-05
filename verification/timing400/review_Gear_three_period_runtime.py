#!/usr/bin/env python3
"""Read retained falling-edge periods and observer history; change no process."""
from datetime import datetime,timezone,timedelta
import json
import math
import os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
point=base/'DCO_domain_nom_tt27_c0_f247_80ns_wire_preconditioned_gear_002'
observer=base/'DCO_Gear_runtime_observer_001'
owner=json.loads((point/'owner.json').read_text());deadline=owner['deadline_uptime']
status=json.loads((point/'status.json').read_text());native=process(status['native_pid'])
assert native['live'] and native['argv'][-1]==str(point/'point.cir')
observer_owner=json.loads((observer/'owner.json').read_text())
assert observer_owner['native_identity']['pid']==status['native_pid']
wave=Path(str(point/'point.cir')+'.prn');falls=[];previous=None;count=0
# Read only complete newline-terminated rows, retaining a prefix copy for audit.
with wave.open('rb') as stream:raw=stream.read()
raw=raw[:raw.rfind(b'\n')+1]
lines=raw.decode().splitlines();assert lines[0].split()==['Index','TIME','V(PLLOUT)','I(VVPWR)']
for line in lines[1:]:
 if 'End of Xyce(TM) Simulation' in line:break
 fields=line.split()
 if not fields:continue
 assert len(fields)==4 and int(fields[0])==count
 row=tuple(map(float,fields[1:]));assert all(map(math.isfinite,row))
 assert previous is None or row[0]>previous[0]
 if previous is not None and previous[1]>.9>=row[1]:
  edge=previous[0]+(.9-previous[1])*(row[0]-previous[0])/(row[1]-previous[1])
  if edge>=5.05e-9:falls.append(edge)
 previous=row;count+=1
assert len(falls)>=4,'three complete falling-edge periods not yet available'
with (observer/'observations.jsonl').open('rb') as stream:history_raw=stream.read()
history_raw=history_raw[:history_raw.rfind(b'\n')+1]
history=[json.loads(line) for line in history_raw.decode().splitlines()]
assert all(h['source_native_pid']==status['native_pid'] for h in history)
assert all(a['uptime']<b['uptime'] and a['simulation_time_s']<=b['simulation_time_s'] for a,b in zip(history,history[1:]))
last=history[-1]
assert time.clock_gettime(time.CLOCK_BOOTTIME)-last['uptime']<90
eligible=[h for h in history if h['uptime']>=last['uptime']-900 and h['simulation_time_s']>=falls[0]]
assert eligible and last['uptime']-eligible[0]['uptime']>=300
first=eligible[0];span=last['uptime']-first['uptime'];advance=last['simulation_time_s']-first['simulation_time_s']
assert span>0 and advance>0
rate=advance/span;target=80e-9
remaining=(target-last['simulation_time_s'])/rate
required_rate=(target-last['simulation_time_s'])/(deadline-last['uptime'])
out=base/'Gear_three_period_runtime_review_001';out.mkdir(exist_ok=False)
(out/'waveform_prefix.prn').write_bytes(raw);(out/'observer_history_prefix.jsonl').write_bytes(history_raw)
proof=dict(observed_utc=datetime.now(timezone.utc).isoformat(),native_identity=native,
    post_reset_falling_edges_s=falls,complete_falling_periods=len(falls)-1,
    last_observer_time_s=last['simulation_time_s'],history_span_s=span,
    observed_ns_per_minute=rate*1e9*60,required_ns_per_minute=required_rate*1e9*60,
    provisional_remaining_hours=remaining/3600,
    provisional_finish_utc=(datetime.fromisoformat(last['observed_utc'])+timedelta(seconds=remaining)).isoformat(),
    projected_within_inherited_deadline=last['uptime']+remaining<=deadline,
    deadline_uptime=deadline,physical_frequency_qualified=False,native_verdict_inferred=False,
    process_started_stopped_or_changed=False,release_qualified=False,
    input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),point/'owner.json',observer/'owner.json',out/'waveform_prefix.prn',out/'observer_history_prefix.jsonl')})
save(out/'assessment.json',proof)
print(json.dumps({k:proof[k] for k in ['complete_falling_periods','observed_ns_per_minute','required_ns_per_minute','provisional_remaining_hours','projected_within_inherited_deadline']}))
