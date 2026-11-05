"""Reserve seven extra physical CPU slots for the existing eight-thread reference pilot."""
import json,os,time
from pathlib import Path
from common import ROOT,save
from resources import identity,lease

if __name__=='__main__':
 parent=ROOT/'build/signoff400/prototype_v3_TT_reference_pilot_002';owner=json.loads((parent/'owner.json').read_text());pid=377645;birth=identity(pid)
 if birth is None or b'prototype_v3_TT_reference_pilot_002' not in Path(f'/proc/{pid}/cmdline').read_bytes():raise SystemExit('original native pilot is not live')
 out=ROOT/'build/signoff400/prototype_v3_reference_throughput_001';out.mkdir(exist_ok=False)
 cores=[];physical=set()
 for core in sorted(os.sched_getaffinity(0)):
  top=Path(f'/sys/devices/system/cpu/cpu{core}/topology');key=((top/'physical_package_id').read_text().strip(),(top/'core_id').read_text().strip())
  if key not in physical:cores.append(core);physical.add(key)
  if len(cores)==8:break
 if len(cores)!=8:raise SystemExit('eight distinct allowed physical cores unavailable')
 save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),native_pid=pid,native_birth=birth,deadline_uptime=owner['deadline_uptime'],extra_cpu_slots=7,total_native_cpu_slots=8,memory_GiB=1))
 with lease(7,1,owner['deadline_uptime']):
  if identity(pid)!=birth:raise SystemExit('original pilot already terminal')
  for task in Path(f'/proc/{pid}/task').iterdir():
   try:os.sched_setaffinity(int(task.name),set(cores))
   except ProcessLookupError:pass
  save(out/'status.json',dict(state='eight_physical_core_throughput_trial_running',physical_cpu_ids=cores,circuit_or_deadline_changed=False,release_ready=False))
  try:
   while identity(pid)==birth and time.clock_gettime(time.CLOCK_BOOTTIME)<owner['deadline_uptime']:time.sleep(5)
  finally:
   if identity(pid)==birth:
    for task in Path(f'/proc/{pid}/task').iterdir():
     try:os.sched_setaffinity(int(task.name),{cores[0]})
     except ProcessLookupError:pass
  save(out/'status.json',dict(state='throughput_reservation_released',native_terminal=identity(pid)!=birth,release_ready=False))
