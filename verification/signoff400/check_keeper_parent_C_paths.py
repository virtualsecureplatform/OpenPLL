"""Bounded exact sufficient path certificate of full parent fixed-supply C."""
import argparse,json,os,sys,time
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from check_prototype_capacitance_paths import certify
from compiled_charge_v2 import execute
from resources import lease,identity


def worker(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['exact_fixed_voltage_congruence']or not r['complete_original_operator_independently_reparsed']:raise ValueError('complete exact supply projection required')
    pairs_file=source/'dynamic.pairs.jsonl';pairs={}
    for line in pairs_file.open():
        row=json.loads(line);key=tuple(row['nodes'])
        if key in pairs:raise ValueError('duplicate capacitor pair')
        pairs[key]=F(row['farads'])
    result=certify(pairs);save(output/'proof.json',result)


def run(source,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=8,automatic_identical_retry=False))
    receipt=source/'assessment.json';pairs=source/'dynamic.pairs.jsonl';folder=Path(__file__).resolve().parent
    files=[receipt,pairs,Path(__file__).resolve(),folder/'check_prototype_capacitance_paths.py'];pins={str(p):sha(p)for p in files};save(output/'inputs.json',dict(input_sha256=pins))
    try:
        save(output/'status.json',dict(state='parent_fixed_C_path_certificate_running',release_ready=False))
        with lease(1,8,deadline):execute([sys.executable,Path(__file__).resolve(),'--source',source,'--output',output,'--worker'],output/'native.log',deadline,8)
        verify(pins);proof=output/'proof.json';r=json.loads(proof.read_text())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(proof):sha(proof)},full_parent_ideal_supply_passivity_certified=r['passivity_certified'],failed_sufficient_certificate_is_not_indefiniteness=True,models_modified=False,wire_R_inserted=False,parent_loading_complete=False,release_ready=False))
        save(output/'status.json',dict(state='parent_C_path_certificate_complete',passivity_certified=r['passivity_certified'],release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_certificate',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',action='store_true');a=p.parse_args()
    (worker if a.worker else run)(a.source.resolve(),a.output.resolve())
